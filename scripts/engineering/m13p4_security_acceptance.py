#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Read-only candidate preflight and plan; never runs security acceptance tests."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

SECURITY_REFERENCE = "57c69344961196fd89b40e8ffec65c06a1898fce"
REPRODUCER_DIRECTORY = "tests/independent_m13r2"
ORIGINAL_BLOBS = {
    "test_additional_readonly_probes.py": "971e085e798854c292fac12775a7b203c88737da",
    "test_concurrent_assertion_probe.py": "36f566dde633a627a5cf84fbf2f1fd5593c1f43e",
    "test_cross_worker_tracking_probe.py": "bd44917c84faf797569befa6ac2d64604442817e",
    "test_durable_crash_probe.py": "8f290ff7288b6a56c73ca7370176f9205a03d34d",
    "test_m13p_postgres_schema.py": "a0b0953ab261079b28e516760921b5892aa71c63",
    "test_m13p_security_contract_acceptance.py": "99cd279b17c53f01a1f876480a4435b0504ca2e1",
    "test_m13r_migration_roundtrip.py": "f4d5731e9b2792b18a69e1fcfd475164ee4f0898",
    "test_m13r_verified_containment.py": "4d0d984d2a84e53cd503696e2e3b9d3a19ef2ede",
}
CANONICAL_ORIGINS = {
    "https://github.com/Guruprasath-Annadurai/Whitepact",
    "https://github.com/Guruprasath-Annadurai/Whitepact.git",
    "git@github.com:Guruprasath-Annadurai/Whitepact.git",
    "ssh://git@github.com/Guruprasath-Annadurai/Whitepact.git",
}
PLANNED_TESTS = (
    "tests/independent_m13r2/",
    "tests/test_m13r3_security_regression.py",
    "tests/test_m12fs_root_hardening.py",
)


class PreflightError(ValueError):
    """Candidate cannot be used for the proposed independent acceptance plan."""


def git_read(repo: Path, *arguments: str) -> str:
    """Only internally selected read-only git commands are issued here."""
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(repo), *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        # Do not echo Git stderr, which may contain a credential-bearing origin.
        raise PreflightError("Read-only Git inspection failed") from exc
    return result.stdout.strip()


def preflight(repo: Path, candidate: str) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{40}", candidate):
        raise PreflightError("--candidate must be an exact full lowercase 40-character commit SHA")
    if git_read(repo, "rev-parse", "--show-toplevel") != str(repo.resolve()):
        raise PreflightError("--repo must identify the repository root")
    if git_read(repo, "rev-parse", "HEAD") != candidate:
        raise PreflightError("Actual HEAD differs from the requested candidate")
    tree = git_read(repo, "rev-parse", "HEAD^{tree}")
    if not re.fullmatch(r"[0-9a-f]{40}", tree):
        raise PreflightError("Could not resolve candidate tree")
    if git_read(repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise PreflightError("Repository has tracked or untracked changes; candidate must be clean")
    if git_read(repo, "remote", "get-url", "origin") not in CANONICAL_ORIGINS:
        raise PreflightError("Origin is not the canonical Whitepact repository")
    expected = {f"{REPRODUCER_DIRECTORY}/{name}": blob for name, blob in ORIGINAL_BLOBS.items()}
    entries = git_read(repo, "ls-tree", "-r", candidate, "--", REPRODUCER_DIRECTORY)
    actual = {}
    for line in entries.splitlines():
        metadata, separator, path = line.partition("\t")
        fields = metadata.split()
        if not separator or len(fields) != 3 or fields[:2] != ["100644", "blob"]:
            raise PreflightError("Original reproducer manifest has an unsupported entry")
        actual[path] = fields[2]
    if actual != expected:
        raise PreflightError(
            "Original reproducer files differ from the pinned M13-R3 blob manifest"
        )
    for path in PLANNED_TESTS[1:]:
        if not git_read(repo, "ls-tree", candidate, "--", path):
            raise PreflightError("A required planned regression suite is missing")
    # A second identity/cleanliness check catches changes during inspection.
    if git_read(repo, "rev-parse", "HEAD") != candidate or git_read(
        repo, "status", "--porcelain=v1", "--untracked-files=all"
    ):
        raise PreflightError("Candidate changed during preflight")
    return {
        "preflight": "PASS",
        "acceptance": "BLOCKED",
        "execution": "NOT EXECUTED",
        "production": "GLOBAL PRODUCTION NO-GO",
        "candidate": candidate,
        "tree": tree,
        "security_reference": SECURITY_REFERENCE,
        "original_reproducer_blobs": expected,
        "repository": str(repo.resolve()),
        "planned_command": shlex.join(
            ["python", "-m", "pytest", *PLANNED_TESTS, "-o", "addopts=", "-v"]
        ),
        "conditions": [
            "Independent reviewer authorization and disposable PostgreSQL required",
            "Recheck HEAD, tree and cleanliness immediately before and after later execution",
            "Security-owned source qualification is not assessed by this read-only preflight",
            "M13-S4 findings and unified-candidate review remain required",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--candidate", required=True)
    arguments = parser.parse_args(argv)
    try:
        report = preflight(arguments.repo.resolve(), arguments.candidate)
    except PreflightError as exc:
        print(
            json.dumps(
                {
                    "preflight": "REFUSED",
                    "acceptance": "BLOCKED",
                    "execution": "NOT EXECUTED",
                    "reason": str(exc),
                }
            )
        )
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
