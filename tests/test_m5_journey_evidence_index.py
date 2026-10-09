# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Customer / enterprise / security-admin journey evidence index."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

JOURNEY_ANCHORS: tuple[tuple[str, str], ...] = (
    ("Customer web policy", "tests/test_web_policy_management.py"),
    ("Customer journey e2e", "tests/js/customer-journey.e2e.mjs"),
    ("Enterprise IAM", "tests/test_iam_adversarial_matrix.py"),
    ("Enterprise SCIM", "tests/test_scim_and_session_lifecycle.py"),
    ("SIEM export", "tests/test_siem_audit_export.py"),
    ("Security TOTP", "tests/test_totp_matched_counter_security.py"),
)


@pytest.mark.parametrize("label, relpath", JOURNEY_ANCHORS)
def test_journey_anchor_present(label: str, relpath: str) -> None:
    path = ROOT / relpath
    assert path.is_file(), f"{label}: missing {relpath}"


def test_enterprise_runbooks_indexed() -> None:
    index = ROOT / "docs" / "operations" / "OPERATOR_RUNBOOK_INDEX.md"
    assert index.is_file()
    text = index.read_text(encoding="utf-8")
    assert "SSO" in text or "SCIM" in text
