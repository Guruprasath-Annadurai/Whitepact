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


def blob_hash(data: bytes) -> str:
    # Reproduce Git's object identifier, not a signature or password digest.
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + bytes([0]) + data, usedforsecurity=False
    ).hexdigest()


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
        verify_pair(path, before, after, expected)
        verified[path] = {"original": expected[0], "revised": expected[1]}
    return verified


if __name__ == "__main__":
    records = verify_repository(Path(__file__).resolve().parents[2])
    print(
        f"Verified {len(records)} exact formatting relationships; independent acceptance pending."
    )
