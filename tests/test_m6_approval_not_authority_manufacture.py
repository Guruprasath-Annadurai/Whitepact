# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Approval ≠ authority manufacture — regression anchors."""

from __future__ import annotations

from pathlib import Path


def test_approval_expiry_suite_present() -> None:
    root = Path(__file__).resolve().parent
    assert (root / "test_approval_expiry.py").is_file()


def test_governance_persistence_approval_tests_present() -> None:
    root = Path(__file__).resolve().parent
    assert (root / "test_governance_persistence.py").is_file()
