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
import tempfile
from pathlib import Path


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=20, check=False)


def posix_acl_enforced() -> bool:
    """Grant UID 65534 read, prove that user can read, then remove the grant."""
    if shutil.which("setfacl") is None or shutil.which("sudo") is None:
        return False
    directory = tempfile.mkdtemp(prefix="wp-acl-proof-")
    try:
        path = Path(directory) / "secret.txt"
        path.write_text("acl-proof", encoding="utf-8")
        os.chmod(directory, 0o700)
        os.chmod(path, 0o600)
        if _run(["setfacl", "-m", "u:65534:rx", directory]).returncode != 0:
            return False
        if _run(["setfacl", "-m", "u:65534:r", str(path)]).returncode != 0:
            return False
        allowed = _run(["sudo", "-n", "-u", "#65534", "cat", str(path)])
        if allowed.returncode != 0 or allowed.stdout != "acl-proof":
            return False
        if _run(["setfacl", "-x", "u:65534", str(path)]).returncode != 0:
            return False
        denied = _run(["sudo", "-n", "-u", "#65534", "cat", str(path)])
        return denied.returncode != 0
    finally:
        shutil.rmtree(directory, ignore_errors=True)


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
    admitted = None
    admission_error = None
    if docker_ok and docker:
        try:
            from responsibleai.isolation.container_backend import DockerContainerBackend
            from responsibleai.isolation.image_admission import admit_image

            DockerContainerBackend(image_name=image, docker_cmd=docker).preflight()
            admitted = admit_image(docker, image)
            digest = admitted.image_id
        except Exception as error:
            admission_error = type(error).__name__
    return {
        "format": "WHITEPACT-M13-STAGE19-HOST-PROBE-V1",
        "kernel": platform.release(),
        "system": platform.system(),
        "machine": platform.machine(),
        "euid": os.geteuid(),
        "setfacl": acl,
        "getfacl": getfacl,
        "posix_acl_enforced": posix_acl_enforced(),
        "digest_admission_enforced": admitted is not None,
        "image_admission_error_type": admission_error,
        "image_reference": admitted.reference if admitted else None,
        "registry_manifest_approved": bool(admitted and "@" in admitted.reference),
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
    if not evidence["setfacl"] or not evidence["getfacl"] or not evidence["posix_acl_enforced"]:
        raise SystemExit(
            "Stage 19 qualification refuses a host whose POSIX ACL grant does not work"
        )
    if not evidence["docker_reachable"]:
        raise SystemExit("Stage 19 qualification refuses a host whose Docker daemon is unreachable")
    if evidence["unisolated_execution_requested"]:
        raise SystemExit("Stage 19 qualification refuses unisolated execution")
    if not evidence["digest_admission_enforced"]:
        raise SystemExit("Stage 19 qualification requires enforced immutable image approval")
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
