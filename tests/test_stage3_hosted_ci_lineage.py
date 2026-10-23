# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Immutable source receipts for the bounded hosted CI fixture dispositions."""

import subprocess
from pathlib import Path

import pytest
from scripts.engineering.m13_approved_formatting import blob_hash


@pytest.mark.parametrize(
    "name,expected",
    [
        ("test_m13_apex_organization.py", "73875e6c663edffea7cd42fd73b721a4598d7b9a"),
        ("test_m13p4_inventory_read_contract.py", "ba7cf315e76ce20e4e9586150290085411e0a47d"),
        ("test_m13_runtime_schema_compatibility.py", "4884e12612da2b1235e0eb9b18da700bc7f7ed40"),
        ("test_tenant_deletion.py", "99058c95a9811eebb7dcf61b283c063f18001728"),
        ("test_sovereign_authority.py", "18f37bb87fbcd5ca2cfb51c88515f9744cc23e72"),
    ],
)
def test_hosted_ci_original_source_is_recoverable_and_exact(name, expected):
    source = Path(__file__).parent / "historical_evidence" / f"hosted_ci_{name}.txt"
    assert blob_hash(source.read_bytes()) == expected


def test_original_distributed_revocation_blob_remains_recoverable():
    original = "e809fdf6922177d4dc89a069e06d9d868772fd8f"
    result = subprocess.run(
        ["git", "cat-file", "blob", original],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        timeout=20,
    )
    assert blob_hash(result.stdout) == original
