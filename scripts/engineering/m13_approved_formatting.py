#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Exact founder-approved formatting relationships; never an evidence waiver."""

import ast
import hashlib
import io
import subprocess
import tokenize
from pathlib import Path

ORIGINAL_COMMIT = "e4f3f12862712762f0d16d561afbd195067606e3"
# Fixed allowlist recorded before running Ruff 0.17.0.
APPROVED = {
    "src/responsibleai/db/engine.py": (
        "be9a6a5d43126468435a924d8f6ea9564ce6676d",
        "35b7abf1ebdd04f57be4d45b6480e795a0b6cf11",
    ),
    "tests/test_container_cleanup_race_adversarial.py": (
        "67fdcdc2fd38a8be252215feb1d45da850143a2c",
        "b7d7821e995e42a3e7de2509a089a09e8677356e",
    ),
    "tests/test_customer_root_authority_bootstrap.py": (
        "696d7312839feffa4c84b1092da6a1241592e2e8",
        "b475ec652bf852ddbc0cb0d00cbc9e45908e862d",
    ),
    "tests/test_h2_linux_containment_adversarial.py": (
        "128e8101173576e3d82fb30d9df469142bc2336a",
        "591d6c85239ff8cb4ea0b55f4beac24319a6833f",
    ),
    "tests/test_h3_audit_evidence_adversarial.py": (
        "857b613c5daf4d33dfb19f5eb379d46c87291a8b",
        "821d95c0f0451dd961255be99a404f134294030e",
    ),
    "tests/test_m12fs_root_hardening.py": (
        "81e838c9ce2f9f1510b0e8076a4b9d6764e44dba",
        "a2238c4269ab81b2d26c04384f34acde04a56ac2",
    ),
    "tests/test_m13_absolute_native_runtime.py": (
        "b129ee565c13232688721af8d3af57e2733e77cc",
        "34096d74d034ff72fa71954092bf256eda25808a",
    ),
    "tests/test_m13_recovery_zero_p0_reproducers.py": (
        "435f4d26c04d9724ee745a3410cb4b3f79931f18",
        "e1b3529d55dd9bc883af79867b8ca0a997b50d0c",
    ),
    "tests/test_m13r3_security_regression.py": (
        "712a6056a280a015dbf0e185e393c79e5281635d",
        "57a50ced55ea8e929974ee434410dcf810d52653",
    ),
    "tests/test_m13s_security_regression.py": (
        "ec36400f35e33df8e8790a8bcd9eca3590a0f166",
        "c7f88c32eb00c61c95e499b1e226bc5b526f8ab2",
    ),
    "tests/test_p0_approval_resume_adversarial.py": (
        "6e3199f82bed8bf2c76d8f7ed2187ac267d6f42d",
        "e0b5271986033f983ef75a2547174757ef7a9885",
    ),
    "tests/test_p0_linux_containment.py": (
        "85c5bee7bf7e78c3d82200e46869cc71f7297822",
        "988f1f471b862ec1aa3d9fa2d35136dcc1b06e70",
    ),
    "tests/test_p0_revocation_outage.py": (
        "93120238040185d86146ca749d2f93668fc1f541",
        "d16b24a0df1f261cb65ca61f294da1806b34d3d7",
    ),
    "tests/test_production_branch_campaign_batch4.py": (
        "1d94c3649b5c2ba8641bac5af13a3ad9e31dd143",
        "0b38a2d7db6f5d1392ef803bd0cd485c454299c7",
    ),
}


class FormattingEvidenceError(ValueError):
    """Original evidence or authorized formatting relationship cannot be verified."""


STAGE3_ENGINE_BLOB = "22d2580db239dcca1fd60646b0cab7e9042fc130"
IDENTITY_SESSION_ENGINE_BLOB = "9cce74dbcd614facd309557fcc929bb69dcd2f10"
ENGINE_PATH = "src/responsibleai/db/engine.py"
STAGE3_SECURITY_FIXTURE_PATH = "tests/test_m13s_security_regression.py"
STAGE3_SECURITY_FIXTURE_BLOB = "41ca7e4ea8ec0f415b92443970d45abd34b901ea"
STAGE3_ROOT_FIXTURE_PATH = "tests/test_m12fs_root_hardening.py"
STAGE3_ROOT_FIXTURE_BLOB = "aff5b71087a2ff11c08df6c4825178afcdd0d8fc"


def historical_blob(repo: Path, identity: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "cat-file", "blob", identity],
            cwd=repo,
            check=True,
            capture_output=True,
            timeout=20,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise FormattingEvidenceError("Missing immutable schema evidence") from exc
    if blob_hash(result) != identity:
        raise FormattingEvidenceError("Incorrect immutable schema evidence")
    return result


def verify_stage3_schema(repo: Path, before: bytes, candidate: bytes):
    formatted = historical_blob(repo, APPROVED[ENGINE_PATH][1])
    approved = historical_blob(repo, STAGE3_ENGINE_BLOB)
    verify_pair(ENGINE_PATH, before, formatted, APPROVED[ENGINE_PATH])
    if blob_hash(candidate) != STAGE3_ENGINE_BLOB or candidate != approved:
        raise FormattingEvidenceError("Unknown Stage 3 schema content")
    start = approved.index(b"tenant_provisioning_records = Table(\n")
    end = approved.index(b"runtime_containment_records = Table(\n", start)
    insertion = approved[start:end]
    if approved[:start] + approved[end:] != formatted:
        raise FormattingEvidenceError("Schema insertion changes existing source")
    declarations = ast.parse(insertion, type_comments=True).body
    names = [
        node.targets[0].id
        for node in declarations
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    ]
    if len(declarations) != 2 or names != [
        "tenant_provisioning_records",
        "tenant_provisioning_outbox",
    ]:
        raise FormattingEvidenceError("Unexpected schema declarations")
    reduced = ast.parse(approved[:start] + approved[end:], type_comments=True)
    if ast.dump(reduced) != ast.dump(ast.parse(formatted, type_comments=True)):
        raise FormattingEvidenceError("Existing schema AST changed")


def blob_hash(data: bytes) -> str:
    # Reproduce Git's object identifier, not a signature or password digest.
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + bytes([0]) + data, usedforsecurity=False
    ).hexdigest()


def verify_identity_session_schema(repo: Path, before: bytes, candidate: bytes):
    """Separate CTO-approved five-line successor; old approvals are unchanged."""
    stage3 = historical_blob(repo, STAGE3_ENGINE_BLOB)
    verify_stage3_schema(repo, before, stage3)
    approved = historical_blob(repo, IDENTITY_SESSION_ENGINE_BLOB)
    if blob_hash(candidate) != IDENTITY_SESSION_ENGINE_BLOB or candidate != approved:
        raise FormattingEvidenceError("Unknown identity-session schema successor")
    insertion = (
        b"    UniqueConstraint(\n"
        b'        "provider",\n'
        b'        "provider_reference_id",\n'
        b'        name="uq_identity_verification_provider_session",\n'
        b"    ),\n"
    )
    anchor = b'    Index("idx_identity_verifications_provider_ref", "provider", "provider_reference_id"),\n'
    if stage3.count(anchor) != 1 or candidate.count(insertion) != 1:
        raise FormattingEvidenceError("Unique approved identity insertion required")
    position = stage3.index(anchor) + len(anchor)
    if candidate != stage3[:position] + insertion + stage3[position:]:
        raise FormattingEvidenceError("Identity insertion changes historical source or placement")
    if candidate[:position] + candidate[position + len(insertion) :] != stage3:
        raise FormattingEvidenceError("Identity insertion cannot reconstruct Stage 3 bytes")
    old, new = ast.parse(stage3, type_comments=True), ast.parse(candidate, type_comments=True)
    tables = [
        node
        for node in new.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "identity_verifications"
    ]
    expected = ast.parse(
        'UniqueConstraint("provider", "provider_reference_id", name="uq_identity_verification_provider_session")',
        mode="eval",
    ).body
    if len(tables) != 1 or not isinstance(tables[0].value, ast.Call):
        raise FormattingEvidenceError("Exact identity table required")
    table = tables[0].value
    matches = [
        index for index, node in enumerate(table.args) if ast.dump(node) == ast.dump(expected)
    ]
    if len(matches) != 1 or matches[0] != len(table.args) - 1:
        raise FormattingEvidenceError("Exact single identity constraint AST required")
    del table.args[matches[0]]
    if ast.dump(new) != ast.dump(old):
        raise FormattingEvidenceError("Identity successor changes other executable AST")


def verify_stage3_security_fixture(repo: Path, before: bytes, candidate: bytes):
    """Separate CTO-approved helper chain; never a formatting-only exception."""
    path = STAGE3_SECURITY_FIXTURE_PATH
    formatted = historical_blob(repo, APPROVED[path][1])
    approved = historical_blob(repo, STAGE3_SECURITY_FIXTURE_BLOB)
    verify_pair(path, before, formatted, APPROVED[path])
    if blob_hash(candidate) != STAGE3_SECURITY_FIXTURE_BLOB or candidate != approved:
        raise FormattingEvidenceError("Unknown Stage 3 security fixture content")

    def span(source):
        module = ast.parse(source, type_comments=True)
        helpers = [
            node
            for node in module.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_setup_postgres_workspace"
        ]
        if len(helpers) != 1:
            raise FormattingEvidenceError("Unique approved provisioning helper required")
        node = helpers[0]
        if node.decorator_list:
            raise FormattingEvidenceError("Unapproved fixture decorator")
        lines = source.splitlines(keepends=True)
        return lines, node.lineno - 1, node.end_lineno

    old_lines, old_start, old_end = span(formatted)
    new_lines, new_start, new_end = span(approved)
    restored = b"".join(new_lines[:new_start] + old_lines[old_start:old_end] + new_lines[new_end:])
    if restored != formatted:
        raise FormattingEvidenceError("Security fixture changes source outside the approved helper")
    # Exact source equality above includes every historical test, assertion,
    # timeout, comment, import and directive outside the one authorized helper.
    if ast.dump(ast.parse(restored, type_comments=True)) != ast.dump(
        ast.parse(formatted, type_comments=True)
    ):
        raise FormattingEvidenceError("Historical security AST changed")


def verify_stage3_root_fixtures(repo: Path, before: bytes, candidate: bytes):
    """Exact two-fixture authorization, separate from immutable formatting approval."""
    path = STAGE3_ROOT_FIXTURE_PATH
    formatted = historical_blob(repo, APPROVED[path][1])
    approved = historical_blob(repo, STAGE3_ROOT_FIXTURE_BLOB)
    verify_pair(path, before, formatted, APPROVED[path])
    if blob_hash(candidate) != STAGE3_ROOT_FIXTURE_BLOB or candidate != approved:
        raise FormattingEvidenceError("Unknown Stage 3 root fixture content")

    def spans(source):
        result = {}
        for node in ast.parse(source, type_comments=True).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
                "_configure_test_env",
                "_create_test_owner",
            }:
                if node.name in result:
                    raise FormattingEvidenceError("Duplicate root fixture")
                result[node.name] = node
        if len(result) != 2:
            raise FormattingEvidenceError("Both approved root fixtures required")
        return result

    original_nodes, revised_nodes = spans(formatted), spans(approved)
    original_lines = formatted.splitlines(keepends=True)
    restored_lines = approved.splitlines(keepends=True)
    for name, node in sorted(revised_nodes.items(), key=lambda pair: pair[1].lineno, reverse=True):
        old = original_nodes[name]
        if [ast.dump(item) for item in old.decorator_list] != [
            ast.dump(item) for item in node.decorator_list
        ]:
            raise FormattingEvidenceError("Root fixture decorators changed")
        restored_lines[node.lineno - 1 : node.end_lineno] = original_lines[
            old.lineno - 1 : old.end_lineno
        ]
    restored = b"".join(restored_lines)
    if restored != formatted:
        raise FormattingEvidenceError("Changes outside approved root fixtures")
    if ast.dump(ast.parse(restored, type_comments=True)) != ast.dump(
        ast.parse(formatted, type_comments=True)
    ):
        raise FormattingEvidenceError("Historical root security AST changed")


def verify_pair(path, before, after, expected):
    if (blob_hash(before), blob_hash(after)) != expected:
        raise FormattingEvidenceError(f"Unknown original/revised content: {path}")
    try:
        old = ast.parse(before, type_comments=True)
        new = ast.parse(after, type_comments=True)

        def comments(data):
            return [
                token.string
                for token in tokenize.tokenize(io.BytesIO(data).readline)
                if token.type == tokenize.COMMENT
            ]

        if ast.dump(old) != ast.dump(new) or comments(before) != comments(after):
            raise FormattingEvidenceError(f"Non-formatting change: {path}")
    except (SyntaxError, tokenize.TokenError, UnicodeError) as exc:
        raise FormattingEvidenceError(f"Unreadable Python evidence: {path}") from exc


def verify_repository(repo: Path):
    verified = {}
    for path, expected in APPROVED.items():
        candidate = repo / path
        if candidate.is_symlink():
            raise FormattingEvidenceError(f"Symlink is not source evidence: {path}")
        try:
            before = subprocess.run(
                ["git", "show", f"{ORIGINAL_COMMIT}:{path}"],
                cwd=repo,
                check=True,
                capture_output=True,
                timeout=20,
            ).stdout
            after = candidate.read_bytes()
        except (OSError, subprocess.SubprocessError) as exc:
            raise FormattingEvidenceError(f"Missing original/candidate evidence: {path}") from exc
        if path == ENGINE_PATH:
            if blob_hash(after) == STAGE3_ENGINE_BLOB:
                verify_stage3_schema(repo, before, after)
            else:
                verify_identity_session_schema(repo, before, after)
        elif path == STAGE3_SECURITY_FIXTURE_PATH:
            verify_stage3_security_fixture(repo, before, after)
        elif path == STAGE3_ROOT_FIXTURE_PATH:
            verify_stage3_root_fixtures(repo, before, after)
        else:
            verify_pair(path, before, after, expected)
        verified[path] = {"original": expected[0], "revised": expected[1]}
        if path == ENGINE_PATH:
            verified[path]["stage3"] = STAGE3_ENGINE_BLOB
            if blob_hash(after) == IDENTITY_SESSION_ENGINE_BLOB:
                verified[path]["identity_session_successor"] = IDENTITY_SESSION_ENGINE_BLOB
        elif path == STAGE3_SECURITY_FIXTURE_PATH:
            verified[path]["stage3_fixture"] = STAGE3_SECURITY_FIXTURE_BLOB
        elif path == STAGE3_ROOT_FIXTURE_PATH:
            verified[path]["stage3_fixture"] = STAGE3_ROOT_FIXTURE_BLOB
    return verified


if __name__ == "__main__":
    records = verify_repository(Path(__file__).resolve().parents[2])
    print(
        f"Verified {len(records)} exact formatting relationships; independent acceptance pending."
    )
