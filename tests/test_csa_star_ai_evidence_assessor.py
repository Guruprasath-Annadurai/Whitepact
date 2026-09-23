# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from scripts.csa_star_ai.evidence_assessor import assess_row, second_pass_challenge
from scripts.csa_star_ai.ledger import ControlAnswer, EvidenceStrength, RemediationLedgerRow


def test_doc_only_downgrade_from_legacy_yes() -> None:
    row = RemediationLedgerRow(
        control_id="A&A-01.1",
        question_id="A&A-01.1",
        question="Are audit and assurance policies established?",
    )
    hint = (
        "Yes",
        "CSP-owned",
        "Documented in compliance/INTERNAL_SECURITY_REVIEW.md and THREAT_MODEL.md only.",
    )
    out = assess_row(row, hint)
    assert out.response == ControlAnswer.NO
    assert out.evidence_strength == EvidenceStrength.WEAK


def test_strong_yes_with_src_and_tests() -> None:
    row = RemediationLedgerRow(
        control_id="AIS-11.1",
        question_id="AIS-11.1",
        question="Are the security boundaries for agents established?",
    )
    hint = (
        "Yes",
        "CSP-owned",
        "Agent boundaries: src/responsibleai/runtime/authority_kernel.py; "
        "tests/test_phase7a_authority_kernel.py.",
    )
    out = assess_row(row, hint)
    assert out.response == ControlAnswer.YES
    assert out.evidence_strength == EvidenceStrength.STRONG
    challenged = second_pass_challenge(out)
    assert challenged.response == ControlAnswer.YES


def test_physical_na_heuristic() -> None:
    row = RemediationLedgerRow(
        control_id="DCS-99.9",
        question_id="DCS-99.9",
        question="Are guards and CCTV used for physical access to the data center?",
    )
    out = assess_row(row, None)
    assert out.response == ControlAnswer.NA
