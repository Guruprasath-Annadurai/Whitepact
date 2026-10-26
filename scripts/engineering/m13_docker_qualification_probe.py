# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Bounded read-only CI availability evidence; NEVER execution/recovery authority.

Do not retry, restart Docker, adopt workloads, change timeouts or clear tracking.
Runtime inventory and daemon identity checks remain independently mandatory.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

INFO_FIELDS = (
    "ID",
    "ServerVersion",
    "Driver",
    "OSType",
    "Architecture",
    "OperatingSystem",
    "KernelVersion",
    "CgroupDriver",
    "CgroupVersion",
    "NCPU",
    "MemTotal",
    "DockerRootDir",
    "SecurityOptions",
)


def collect(phase):
    report = {
        "format": "WHITEPACT_CI_DOCKER_PROBE_V1",
        "phase": phase,
        "execution_authority": False,
        "ready": False,
        "runner": {
            name: os.environ.get(name)
            for name in (
                "RUNNER_OS",
                "RUNNER_ARCH",
                "RUNNER_ENVIRONMENT",
                "ImageOS",
                "ImageVersion",
            )
        },
        "commands": [],
    }

    def command(arguments):
        start = time.monotonic()
        record = {"command": arguments, "timeout_seconds": 10, "ok": False}
        try:
            result = subprocess.run(
                arguments, capture_output=True, text=True, timeout=10, check=False
            )
            record["returncode"] = result.returncode
            record["stderr_sha256"] = hashlib.sha256(result.stderr.encode()).hexdigest()
            record["stderr_bytes"] = len(result.stderr.encode())
            record["ok"] = result.returncode == 0
            return result.stdout if record["ok"] else None
        except (OSError, subprocess.TimeoutExpired) as error:
            record["error_type"] = type(error).__name__
            return None
        finally:
            record["elapsed_seconds"] = round(time.monotonic() - start, 6)
            report["commands"].append(record)

    docker = shutil.which("docker") or "docker"
    info = command([docker, "info", "--format", "{{json .}}"])
    identity = command([docker, "info", "--format", "{{.ID}}"])
    inventory = command([docker, "ps", "--all", "--no-trunc", "--format", "{{json .}}"])
    version = command([docker, "version", "--format", "{{json .Client}}"])
    try:
        if any(value is None for value in (info, identity, inventory, version)):
            raise ValueError("Required Docker observation unavailable")
        parsed = json.loads(info)
        observed = identity.strip()
        if (
            not isinstance(parsed, dict)
            or not re.fullmatch(r"[A-Za-z0-9:_-]{1,128}", observed)
            or parsed.get("ID") != observed
        ):
            raise ValueError("Missing, invalid or changing daemon identity")
        rows = [json.loads(line) for line in inventory.splitlines()]
        if any(
            not isinstance(row, dict)
            or not isinstance(row.get("ID"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", row["ID"])
            for row in rows
        ):
            raise ValueError("Unverifiable inventory")
        client = json.loads(version)
        if not isinstance(client, dict):
            raise ValueError("Invalid client version evidence")
        report["daemon_identity"] = observed
        report["daemon"] = {name: parsed.get(name) for name in INFO_FIELDS}
        report["client"] = {
            name: client.get(name) for name in ("Version", "ApiVersion", "GoVersion", "Os", "Arch")
        }
        report["inventory"] = [
            {name: row.get(name) for name in ("ID", "Names", "Image", "State")} for row in rows
        ]
        report["ready"] = True
    except (TypeError, ValueError, KeyError):
        report["validation_error"] = "Required Docker availability evidence is unverified"
    systemctl = shutil.which("systemctl")
    if systemctl:
        service = command(
            [
                systemctl,
                "show",
                "docker",
                "--property=ActiveState,SubState,Result,ExecMainStatus,NRestarts",
            ]
        )
        report["service"] = {}
        for line in (service or "").splitlines():
            key, separator, value = line.partition("=")
            if separator and key in {
                "ActiveState",
                "SubState",
                "Result",
                "ExecMainStatus",
                "NRestarts",
            }:
                report["service"][key] = value
    report["pressure"] = {}
    for resource in ("cpu", "memory", "io"):
        try:
            report["pressure"][resource] = Path(f"/proc/pressure/{resource}").read_text()[:1024]
        except OSError:
            report["pressure"][resource] = None
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    options = parser.parse_args()
    report = collect(options.phase)
    if options.phase == "after":
        try:
            if options.baseline is None:
                raise ValueError("Before receipt required")
            before = json.loads(options.baseline.read_text())
            if (
                before.get("ready") is not True
                or not report["ready"]
                or before.get("daemon_identity") != report.get("daemon_identity")
            ):
                raise ValueError("Unverified or changed daemon")
        except (OSError, ValueError, AttributeError):
            report["ready"] = False
            report["baseline_error"] = "Before receipt is absent, unverified or changed"
    options.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(f"Docker CI availability: {'PASS' if report['ready'] else 'FAIL'}; {options.output}")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
