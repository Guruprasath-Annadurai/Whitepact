# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Receipt integrity tests; these are not customer journey acceptance."""

import subprocess
from pathlib import Path

import pytest
from scripts.engineering.m13_apex_customer_journey import PHASES, validate_evidence


def receipt():
    return {
        "authority_seeded": False,
        "acceptance": "BLOCKED",
        "stages": [
            {"phase": phase, "status": "PASS" if index < 7 else "NOT_EXECUTED"}
            for index, phase in enumerate(PHASES)
        ],
    }


def test_incomplete_receipt_cannot_claim_success():
    evidence = receipt()
    validate_evidence(evidence)
    evidence["acceptance"] = "PASS"
    with pytest.raises(ValueError, match="contradicts"):
        validate_evidence(evidence)


def test_seeded_authority_cannot_qualify():
    evidence = receipt()
    evidence["authority_seeded"] = True
    with pytest.raises(ValueError, match="Seeded"):
        validate_evidence(evidence)


def test_success_after_missing_prerequisite_is_rejected():
    evidence = receipt()
    evidence["stages"][10]["status"] = "PASS"
    with pytest.raises(ValueError, match="boundary"):
        validate_evidence(evidence)


def test_duplicate_stages_are_rejected():
    evidence = receipt()
    evidence["stages"][24] = evidence["stages"][0]
    with pytest.raises(ValueError, match="distinct"):
        validate_evidence(evidence)


def test_root_initiation_can_precede_consent_persistence_without_claiming_root_success():
    evidence = receipt()
    for stage in evidence["stages"]:
        if stage["phase"] in {"legitimate_identity_qualification", "root_initiation"}:
            stage["status"] = "PASS"
    validate_evidence(evidence)


def test_revocation_denial_rejects_false_pass_responses():
    """Component refusal contract. A passing result is not customer acceptance."""
    script = Path(__file__).resolve().parents[0] / "js" / "revocation-denial.test.mjs"
    completed = subprocess.run(
        ["node", "--test", str(script)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_root_activation_requires_persisted_consent():
    evidence = receipt()
    for stage in evidence["stages"]:
        if stage["phase"] in {
            "legitimate_identity_qualification",
            "root_initiation",
            "root_proof_of_possession",
            "root_activation",
        }:
            stage["status"] = "PASS"
    with pytest.raises(ValueError, match="boundary"):
        validate_evidence(evidence)
