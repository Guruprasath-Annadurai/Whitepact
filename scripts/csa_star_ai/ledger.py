# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Internal remediation ledger schema for AI-CAIQ v1.1."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RemediationCategory(StrEnum):
    SOURCE_CODE = "A_SOURCE_CODE"
    INFRASTRUCTURE = "B_INFRASTRUCTURE"
    SECURITY_PROCESS = "C_SECURITY_PROCESS"
    DOCUMENTATION_POLICY = "D_DOCUMENTATION_POLICY"
    CI_SUPPLY_CHAIN = "E_CI_SUPPLY_CHAIN"
    ORGANIZATIONAL = "F_ORGANIZATIONAL"
    CLOUD_SUBPROCESSOR = "G_CLOUD_SUBPROCESSOR"
    CUSTOMER_SHARED = "H_CUSTOMER_SHARED"
    EXTERNAL_THIRD_PARTY = "I_EXTERNAL_THIRD_PARTY"


class ControlAnswer(StrEnum):
    YES = "YES"
    NO = "NO"
    NA = "NA"


class RemediationLedgerRow(BaseModel):
    control_id: str
    domain: str = ""
    question: str
    current_answer: ControlAnswer
    ssrm_owner: str = ""
    current_evidence: str = ""
    gap: str = ""
    remediation: str = ""
    evidence_required: str = ""
    responsible_party: str = ""
    remediation_type: RemediationCategory | str = ""
    status: str = "open"
    final_answer: ControlAnswer | None = None
    final_evidence: str = ""
    customer_responsibility: str = ""
    changed_in_campaign: bool = False


class RemediationLedger(BaseModel):
    framework: str = "CSA AI-CAIQ v1.1"
    base_sha: str = ""
    feature_sha: str = ""
    rows: list[RemediationLedgerRow] = Field(default_factory=list)

    def summary(self) -> dict[str, int]:
        counts = {"YES": 0, "NO": 0, "NA": 0}
        for row in self.rows:
            ans = (row.final_answer or row.current_answer).value
            counts[ans] = counts.get(ans, 0) + 1
        return counts


def row_to_dict(row: RemediationLedgerRow) -> dict[str, Any]:
    return row.model_dump()
