# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Validate locked Terraform modules in an immutable disposable Git archive.

No state backend, plan, apply, credentials or deployment. Provider downloads
need explicit opt-in. Invoke the verified native binary, not HOME-dependent
tfenv wrappers. Python 3.11+; built-in libraries only.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

VERSION = "1.9.8"
# Installed native bytes independently compared with official release archive:
# zip SHA256 873d7b925d08578fb6bb9c12c7cd92ae73e289e07c360f2fdd69f9036b7baaab.
# https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_SHA256SUMS
NATIVE_HASHES = {
    ("Darwin", "arm64"): "7d15d4cae23f0f85ddd543c5455ecf4b7a384386bb5c0f1da83470f5da543b3f",
    # Official linux_amd64 zip SHA256:
    # 186e0145f5e5f2eb97cbd785bc78f21bae4ef15119349f6ad4fa535b83b10df8.
    ("Linux", "x86_64"): "7386e89a97d0f24024955acc79ccf693b75b97f7c6383cb9d966e7d59aa5b223",
}
MODULES = ("cloudflare-edge", "gcp-staging-optional")
ARCHIVE_LIMIT = 128 * 1024 * 1024


def checked_revision(revision: str) -> str:
    if revision != "HEAD" and not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Revision must be HEAD or an exact commit SHA")
    return revision


def verify_binary(binary: Path, expected_hash: str) -> Path:
    resolved = binary.resolve(strict=True)
    if (
        not resolved.is_file()
        or not os.access(resolved, os.X_OK)
        or hashlib.sha256(resolved.read_bytes()).hexdigest() != expected_hash
    ):
        raise ValueError("Native Terraform binary checksum mismatch")
    return resolved


def clean_environment(home: Path) -> dict[str, str]:
    """Do not inherit TF_CLI_ARGS, cloud credentials, tfvars, proxies or secrets."""
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "TMPDIR": str(home),
        "TF_IN_AUTOMATION": "1",
        "TF_INPUT": "0",
        "TF_CLI_CONFIG_FILE": str(home / "terraform.rc"),
        "CHECKPOINT_DISABLE": "1",
        "LANG": "C.UTF-8",
    }


def provider_commands(binary: Path) -> list[list[str]]:
    return [
        [str(binary), "init", "-backend=false", "-lockfile=readonly", "-input=false", "-no-color"],
        [str(binary), "validate", "-json"],
    ]


def extract_archive(data: bytes, destination: Path) -> None:
    if len(data) > ARCHIVE_LIMIT:
        raise ValueError("Git archive exceeds validation size bound")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        members = archive.getmembers()
        if sum(member.size for member in members) > ARCHIVE_LIMIT:
            raise ValueError("Expanded archive exceeds validation size bound")
        for member in members:
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
                raise ValueError("Unsafe Git archive member")
        archive.extractall(destination, members=members, filter="data")


def _command(
    command: list[str], *, cwd: Path, env: dict[str, str], timeout: int
) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, timeout=timeout, check=False
    )


def _failure_class(output: bytes) -> str:
    text = output.decode(errors="replace").lower()
    if "checksum" in text or "signature" in text:
        return "PROVIDER_INTEGRITY"
    if "tls" in text or "certificate" in text:
        return "REGISTRY_TLS"
    if "no such host" in text or "could not connect" in text:
        return "REGISTRY_NETWORK"
    if "plugin" in text and "schema" in text:
        return "LOCAL_PROVIDER_PLUGIN"
    if "lock" in text:
        return "LOCKFILE"
    return "COMMAND_FAILED"


def validation_result(output: object, returncode: int) -> dict:
    """Fail closed on malformed JSON; never emit diagnostic values/source text."""
    if (
        not isinstance(output, dict)
        or output.get("format_version") != "1.0"
        or type(output.get("valid")) is not bool
        or type(output.get("error_count")) is not int
        or type(output.get("warning_count")) is not int
        or output["error_count"] < 0
        or output["warning_count"] < 0
        or not isinstance(output.get("diagnostics"), list)
    ):
        return {"status": "BLOCKED", "failure": "MALFORMED_VALIDATE_OUTPUT"}
    severities = [
        diagnostic.get("severity") if isinstance(diagnostic, dict) else None
        for diagnostic in output["diagnostics"]
    ]
    if (
        any(severity not in ("error", "warning") for severity in severities)
        or severities.count("error") != output["error_count"]
        or severities.count("warning") != output["warning_count"]
    ):
        return {"status": "BLOCKED", "failure": "INCONSISTENT_VALIDATE_OUTPUT"}
    return {
        "status": "PASS"
        if output["valid"] is True and output["error_count"] == 0 and returncode == 0
        else "FAIL",
        "error_count": output["error_count"],
        "warning_count": output["warning_count"],
        "diagnostic_severities": severities,
        "diagnostic_categories": [
            category if category != "COMMAND_FAILED" else "OTHER_DIAGNOSTIC"
            for category in (
                _failure_class(str(diagnostic.get("summary", "")).encode())
                for diagnostic in output["diagnostics"]
            )
        ],
    }


def validate(repo: Path, binary: Path, revision: str = "HEAD", timeout: int = 120) -> dict:
    checked_revision(revision)
    if not 10 <= timeout <= 300:
        raise ValueError("Command timeout must be 10..300 seconds")
    expected = NATIVE_HASHES.get((platform.system(), platform.machine()))
    if expected is None:
        raise ValueError("Native platform has no independently verified binary hash")
    binary = verify_binary(binary, expected)
    repo = repo.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="whitepact-m11-infra-") as temporary:
        temp = Path(temporary)
        home = temp / "home"
        home.mkdir(mode=0o700)
        # No inherited user rc, provider mirror, token or implicit tfenv install.
        (home / "terraform.rc").write_text("disable_checkpoint = true\n", encoding="utf-8")
        env = clean_environment(home)
        version = _command([str(binary), "version", "-json"], cwd=temp, env=env, timeout=timeout)
        if version.returncode or json.loads(version.stdout)["terraform_version"] != VERSION:
            raise ValueError("Pinned native Terraform version verification failed")
        resolved = _command(
            ["/usr/bin/git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
            cwd=repo,
            env=env,
            timeout=timeout,
        )
        if resolved.returncode:
            raise ValueError("Requested Git commit unavailable")
        sha = resolved.stdout.decode().strip()
        tree = _command(
            ["/usr/bin/git", "rev-parse", f"{sha}^{{tree}}"],
            cwd=repo,
            env=env,
            timeout=timeout,
        )
        if tree.returncode:
            raise ValueError("Requested Git tree unavailable")
        archived = _command(
            ["/usr/bin/git", "archive", "--format=tar", sha, "infra/terraform", "deploy"],
            cwd=repo,
            env=env,
            timeout=timeout,
        )
        if archived.returncode:
            raise ValueError("Git archive failed")
        snapshot = temp / "snapshot"
        snapshot.mkdir()
        extract_archive(archived.stdout, snapshot)
        formatted = _command(
            [str(binary), "fmt", "-check", "-recursive", "infra/terraform"],
            cwd=snapshot,
            env=env,
            timeout=timeout,
        )
        modules = snapshot / "infra/terraform/modules"
        results = []
        for module in MODULES:
            directory = modules / module
            lock = directory / ".terraform.lock.hcl"
            before = hashlib.sha256(lock.read_bytes()).hexdigest()
            init_command, validate_command = provider_commands(binary)
            initialized = _command(init_command, cwd=directory, env=env, timeout=timeout)
            item = {
                "module": module,
                "lock_sha256": before,
                "init_exit": initialized.returncode,
                "init_warning_count": (initialized.stdout + initialized.stderr).count(b"Warning:"),
            }
            if initialized.returncode:
                item.update(status="BLOCKED", failure=_failure_class(initialized.stderr))
            else:
                checked = _command(validate_command, cwd=directory, env=env, timeout=timeout)
                item["validate_exit"] = checked.returncode
                try:
                    output = json.loads(checked.stdout)
                except (ValueError, UnicodeError):
                    item.update(status="BLOCKED", failure=_failure_class(checked.stderr))
                else:
                    item.update(validation_result(output, checked.returncode))
            after = hashlib.sha256(lock.read_bytes()).hexdigest()
            item["lock_unchanged"] = before == after
            if before != after:
                item.update(status="FAIL", failure="LOCKFILE_CHANGED")
            results.append(item)
        return {
            "source_head": sha,
            "source_tree": tree.stdout.decode().strip(),
            "validator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "format_exit": formatted.returncode,
            "terraform_version": VERSION,
            "terraform_binary_sha256": expected,
            "targets": results,
            "paid_hetzner_selection": "EXCLUDED",
            "backend_initialized": False,
            "plan_or_apply": False,
            "credentials_inherited": False,
            "source_mutated": False,
            "deployment_ready": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--terraform-binary", type=Path, required=True)
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--allow-provider-download", action="store_true")
    args = parser.parse_args()
    if not args.allow_provider_download:
        parser.error("--allow-provider-download required; no provider or cloud operation performed")
    try:
        result = validate(args.repo, args.terraform_binary, args.revision, args.timeout)
    except Exception as exc:
        # No raw driver/provider diagnostics, paths or environment values on errors.
        print(json.dumps({"status": "BLOCKED", "error_class": type(exc).__name__}))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return (
        0
        if result["format_exit"] == 0
        and all(item["status"] == "PASS" for item in result["targets"])
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
