# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Receipt integrity tests; these are not customer journey acceptance."""

import pytest
from scripts.engineering.m13_apex_customer_journey import validate_evidence


def receipt():
    return {
        "authority_seeded": False,
        "acceptance": "BLOCKED",
        "stages": [
            {"phase": f"stage_{index}", "status": "PASS" if index < 7 else "NOT_EXECUTED"}
            for index in range(24)
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
    evidence["stages"][23] = evidence["stages"][0]
    with pytest.raises(ValueError, match="distinct"):
        validate_evidence(evidence)
