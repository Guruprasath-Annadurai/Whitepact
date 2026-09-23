# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path

from scripts.csa_star_ai.ledger import RemediationLedger, RemediationLedgerRow
from scripts.csa_star_ai.role_scope import analyze_role, apply_role_to_row

REPO = Path(__file__).resolve().parents[1]


def test_mds_marked_na_eligible_not_mp_scope() -> None:
    row = RemediationLedgerRow(
        control_id="MDS-08.1",
        question_id="MDS-08.1",
        domain="MDS",
        question="checksums of model checkpoints",
    )
    ctx = analyze_role(row)
    assert ctx.na_eligible
    assert ctx.role_applicability == "NOT_APPLICABLE_MP_SCOPE"


def test_physical_datacenter_na_eligible() -> None:
    row = RemediationLedgerRow(
        control_id="DCS-17.1",
        question_id="DCS-17.1",
        domain="DCS",
        question="Are data center security metrics established?",
    )
    ctx = analyze_role(row)
    assert ctx.na_eligible


def test_phase2_ledger_has_zero_unclassified() -> None:
    ledger = RemediationLedger.model_validate_json(
        (REPO / "compliance/csa-star-ai/ledger/remediation_ledger.json").read_text()
    )
    uncl = [r for r in ledger.rows if r.phase2_remediation_class == "UNCLASSIFIED"]
    assert not uncl


def test_apply_role_populates_primary_osp() -> None:
    row = RemediationLedgerRow(
        control_id="AIS-11.1",
        question_id="AIS-11.1",
        domain="AIS",
        question="agent boundaries",
    )
    out = apply_role_to_row(row)
    assert out.primary_role == "OSP"
