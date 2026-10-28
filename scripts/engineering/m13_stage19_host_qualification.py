# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Capability probe for the Stage 19 Linux execution host.

This does not approve a production host and does not weaken isolation.
A missing Docker daemon or POSIX ACL tool is a refusal, not a pass.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=20, check=False)


def probe_host() -> dict:
    acl = shutil.which("setfacl")
    getfacl = shutil.which("getfacl")
    docker = shutil.which("docker")
    docker_ok = False
    docker_id = None
    docker_error = None
    if docker:
        info = _run([docker, "info", "--format", "{{.ServerVersion}} {{.ID}}"])
        docker_ok = info.returncode == 0 and bool(info.stdout.strip())
        if docker_ok:
            docker_id = info.stdout.strip().split()[-1]
        else:
            docker_error = (info.stderr or info.stdout).strip()[:300]
    image = os.environ.get("WHITEPACT_ISOLATION_IMAGE", "python:3.11-slim")
    digest = None
    if docker_ok and docker:
        inspected = _run(
            [docker, "image", "inspect", "--format", "{{index .RepoDigests 0}}", image]
        )
        if inspected.returncode == 0:
            digest = inspected.stdout.strip() or None
    return {
        "format": "WHITEPACT-M13-STAGE19-HOST-PROBE-V1",
        "kernel": platform.release(),
        "system": platform.system(),
        "machine": platform.machine(),
        "euid": os.geteuid(),
        "setfacl": acl,
        "getfacl": getfacl,
        "docker": docker,
        "docker_reachable": docker_ok,
        "docker_daemon_id": docker_id,
        "docker_error": docker_error,
        "isolation_image": image,
        "isolation_image_digest": digest,
        "unisolated_execution_requested": os.environ.get("WHITEPACT_ALLOW_UNISOLATED_EXECUTION")
        == "1",
        "production_certified": False,
    }


def require_qualification_host(evidence: dict) -> None:
    if evidence["system"] != "Linux":
        raise SystemExit("Stage 19 qualification refuses a non-Linux host")
    if not evidence["setfacl"] or not evidence["getfacl"]:
        raise SystemExit("Stage 19 qualification refuses a host without POSIX ACL tools")
    if not evidence["docker_reachable"]:
        raise SystemExit("Stage 19 qualification refuses a host whose Docker daemon is unreachable")
    if evidence["unisolated_execution_requested"]:
        raise SystemExit("Stage 19 qualification refuses unisolated execution")
    if not evidence["isolation_image_digest"]:
        raise SystemExit("Stage 19 qualification refuses an image with no recorded digest")


def main() -> None:
    evidence = probe_host()
    destination = Path(os.environ.get("WHITEPACT_STAGE19_EVIDENCE", "artifacts/stage19-host.json"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    require_qualification_host(evidence)
    print(destination)


if __name__ == "__main__":
    main()
