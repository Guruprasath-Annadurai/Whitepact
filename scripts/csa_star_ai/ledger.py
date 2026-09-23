# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Internal remediation ledger schema for AI-CAIQ v1.1."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ControlAnswer(StrEnum):
    YES = "YES"
    NO = "NO"
    NA = "NA"
    UNASSESSED = "UNASSESSED"


class EvidenceStrength(StrEnum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    NONE = "NONE"


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
    UNCLASSIFIED = "UNCLASSIFIED"


class RemediationLedgerRow(BaseModel):
    control_id: str
    question_id: str = ""
    domain: str = ""
    control_title: str = ""
    control_specification: str = ""
    question: str
    applicability: str = "APPLICABLE"
    response: ControlAnswer = ControlAnswer.UNASSESSED
    justification: str = ""
    evidence_references: list[str] = Field(default_factory=list)
    evidence_strength: EvidenceStrength = EvidenceStrength.NONE
    evidence_type: str = ""
    implementation_owner: str = ""
    customer_responsibility: str = ""
    provider_dependency: str = ""
    remediation_requirement: str = ""
    residual_risk: str = ""
    reviewer_notes: str = ""
    remediation_type: RemediationCategory | str = RemediationCategory.UNCLASSIFIED
    status: str = "unassessed"
    preliminary_snapshot_answer: str | None = None
    changed_in_campaign: bool = False
    partial_implementation: bool = False

    # Legacy export columns
    ssrm_owner: str = ""
    implementation_description: str = ""


class RemediationLedger(BaseModel):
    framework: str = "CSA AI-CAIQ v1.1"
    base_sha: str = "acddae1e96050c1dbe3981327f47dc102beb9262"
    feature_sha: str = ""
    upstream_workbook_sha256: str | None = None
    rows: list[RemediationLedgerRow] = Field(default_factory=list)

    def summary(self) -> dict[str, int]:
        counts = {k.value: 0 for k in ControlAnswer}
        for row in self.rows:
            counts[row.response.value] = counts.get(row.response.value, 0) + 1
        return counts

    def applicable_readiness(self) -> tuple[int, int, float]:
        yes = sum(1 for r in self.rows if r.response == ControlAnswer.YES)
        no = sum(1 for r in self.rows if r.response == ControlAnswer.NO)
        na = sum(1 for r in self.rows if r.response == ControlAnswer.NA)
        denom = yes + no
        pct = (yes / denom * 100.0) if denom else 0.0
        return yes, denom, pct

    def evidence_quality_counts(self) -> dict[str, int]:
        out: dict[str, int] = {k.value: 0 for k in EvidenceStrength}
        for row in self.rows:
            if row.response == ControlAnswer.YES:
                out[row.evidence_strength.value] = out.get(row.evidence_strength.value, 0) + 1
        return out


def row_to_dict(row: RemediationLedgerRow) -> dict[str, Any]:
    return row.model_dump()
