#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Read-only candidate preflight and plan; never runs security acceptance tests."""

from __future__ import annotations

import argparse
import ast
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
# Founder-approved import-only corrections, plus the separately approved
# historical 0063->0064 fixture target. Original references above never change.
APPROVED_BLOBS = {
    "test_m13p_postgres_schema.py": "3d46e3616990f3c364e244ae277b74149ceb992c",
    "test_m13p_security_contract_acceptance.py": "cda15e380ecd36b845561644ca8cb8a2fd2a292a",
    "test_m13r_migration_roundtrip.py": "661b08b9150e93babf282294199639592b3384b4",
    "test_m13r_verified_containment.py": "137c337e4a33305f1168e1babf53f44dee0ce362",
}
RUNTIME_REFERENCE = "969c97ae975c6dc271b8d139318a9a91bb2a6f08"
RUNTIME_PATH = "scripts/engineering/reproducers/test_m13_dual_titan_cancellation.py"
RUNTIME_ORIGINAL = "bc00c78e9cafa461b58cde388610b43c5866acfe"
RUNTIME_REVISED = "08e36bbf2c6ac0a412d397ae1c248d816190852a"
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


def verify_authorized_revision(name: str, original: str, revised: str) -> None:
    """Reject every non-import change except two exact historical upgrade targets."""
    try:
        before, after = ast.parse(original), ast.parse(revised)
    except SyntaxError as exc:
        raise PreflightError("Reproducer is not valid Python") from exc
    if name == "test_m13r_migration_roundtrip.py":
        changed = 0
        for function in before.body:
            if (
                getattr(function, "name", None)
                != "test_0063_upgrade_0064_constraints_and_safe_empty_downgrade"
            ):
                continue
            for call in ast.walk(function):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id == "_run_alembic"
                    and len(call.args) == 4
                    and isinstance(call.args[2], ast.Constant)
                    and call.args[2].value == "upgrade"
                    and isinstance(call.args[3], ast.Constant)
                    and call.args[3].value == "head"
                ):
                    call.args[3].value = "0064"
                    changed += 1
        if changed != 2:
            raise PreflightError(
                "Historical fixture reference no longer has two authorized targets"
            )

    def normalized(module):
        imports = sorted(
            ast.dump(node, include_attributes=False)
            for node in module.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        )
        logic = [
            ast.dump(node, include_attributes=False)
            for node in module.body
            if not isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        return imports, logic

    if normalized(before) != normalized(after):
        raise PreflightError("Unauthorized reproducer logic/import modification")


def verify_reproducer_manifest(repo: Path, actual: dict[str, str]) -> None:
    expected = {f"{REPRODUCER_DIRECTORY}/{name}": blob for name, blob in ORIGINAL_BLOBS.items()}
    if actual.keys() != expected.keys():
        raise PreflightError(
            "Original reproducer files differ from the pinned M13-R3 blob manifest"
        )
    for path, original_blob in expected.items():
        if git_read(repo, "rev-parse", f"{SECURITY_REFERENCE}:{path}") != original_blob:
            raise PreflightError(
                "Original historical reproducer evidence is unavailable or changed"
            )
        if actual[path] == original_blob:
            continue
        name = Path(path).name
        if APPROVED_BLOBS.get(name) != actual[path]:
            raise PreflightError(
                "Original reproducer files differ from the pinned M13-R3 blob manifest"
            )
        verify_authorized_revision(
            name,
            git_read(repo, "cat-file", "blob", original_blob),
            git_read(repo, "cat-file", "blob", actual[path]),
        )


def verify_cancellation_revision(original: str, revised: str) -> None:
    before, after = ast.parse(original), ast.parse(revised)
    function = next(
        node
        for node in before.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "test_execute_cleanup_failure_retains_tracking_after_cancellation"
    )
    function.body[1:1] = ast.parse(
        "from responsibleai.isolation.durable_intent import required_journal\n"
        "assert required_journal() is None\n"
    ).body
    position = next(i for i, node in enumerate(function.body) if isinstance(node, ast.With))
    helper = ast.parse(
        "def acknowledge_inert_create(command, receipt):\n"
        '    cid = "c" * 64\n'
        '    receipt.write_text(cid, encoding="utf-8")\n'
        "    return cid\n"
    ).body[0]
    function.body.insert(position, helper)
    operation = function.body[position + 1]
    addition = (
        ast.parse(
            'with patch.object(backend, "_create_stopped_container", '
            "side_effect=acknowledge_inert_create):\n    pass\n"
        )
        .body[0]
        .items[0]
    )
    operation.items.insert(len(operation.items) - 1, addition)
    if ast.dump(before, include_attributes=False) != ast.dump(after, include_attributes=False):
        raise PreflightError("Unauthorized cancellation fixture modification")


def verify_runtime_fixture(repo: Path, candidate: str) -> dict[str, str]:
    original = git_read(repo, "rev-parse", f"{RUNTIME_REFERENCE}:{RUNTIME_PATH}")
    revised = git_read(repo, "rev-parse", f"{candidate}:{RUNTIME_PATH}")
    if original != RUNTIME_ORIGINAL:
        raise PreflightError("Original cancellation evidence is unavailable or changed")
    if revised != original:
        if revised != RUNTIME_REVISED:
            raise PreflightError("Unapproved cancellation fixture blob")
        verify_cancellation_revision(
            git_read(repo, "cat-file", "blob", original),
            git_read(repo, "cat-file", "blob", revised),
        )
    return {
        "original_reference": RUNTIME_REFERENCE,
        "original_blob": original,
        "candidate_blob": revised,
    }


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
    verify_reproducer_manifest(repo, actual)
    runtime_fixture = verify_runtime_fixture(repo, candidate)
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
        "candidate_reproducer_blobs": actual,
        "runtime_fixture_provenance": runtime_fixture,
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
