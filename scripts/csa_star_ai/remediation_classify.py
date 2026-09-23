# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Assign Phase 2 remediation class to every NO row (zero UNCLASSIFIED)."""

from __future__ import annotations

from scripts.csa_star_ai.ledger import ControlAnswer, RemediationLedgerRow
from scripts.csa_star_ai.phase2_categories import Phase2RemediationClass

_ORG_DOMAINS = {"A&A", "GRC", "HRS", "SEF"}
_LEGAL_KEYWORDS = ("privacy", "dpa", "gdpr", "personal data", "counsel", "legal", "statutory")
_ENDPOINT_KEYWORDS = ("endpoint", "workstation", "laptop", "mobile device", "mdm")
_PROD_KEYWORDS = ("production", "restore", "recovery", "backup", "rto", "rpo", "disaster")
_CI_IDS = {
    "DSP-13.1",
    "SEF-08.2",
    "STA-01.1",
    "STA-03.1",
    "STA-08.1",
    "STA-09.1",
    "STA-12.1",
    "STA-14.1",
    "STA-16.1",
}
_PROVIDER_DOMAINS = {"DCS", "I&S", "CCC"}
_SHARED_MARKERS = ("shared", "customer", "tenant", "csc")


def classify_phase2_remediation(row: RemediationLedgerRow) -> Phase2RemediationClass:
    qid = row.question_id
    domain = row.domain or (qid.split("-", 1)[0] if "-" in qid else "")
    q = (row.question or "").casefold()

    if row.response == ControlAnswer.NA or row.na_candidate:
        return Phase2RemediationClass.NOT_APPLICABLE_CANDIDATE

    if qid in _CI_IDS or "supply chain" in q or "sbom" in q or "bill of material" in q:
        return Phase2RemediationClass.CI_SUPPLY_CHAIN

    if domain == "MDS" or qid.startswith("MDS"):
        return Phase2RemediationClass.MODEL_PROVIDER

    if any(k in q for k in _LEGAL_KEYWORDS) or domain == "IPY":
        return Phase2RemediationClass.LEGAL_PRIVACY

    if any(k in q for k in _ENDPOINT_KEYWORDS):
        return Phase2RemediationClass.ENDPOINT_SECURITY

    if row.role_applicability == "APPLICABLE_VENDOR_ASSURANCE" or domain in _PROVIDER_DOMAINS:
        if "whitepact" in q and "provider" not in q:
            pass
        if any(
            k in q
            for k in (
                "datacenter",
                "data center",
                "physical",
                "hypervisor",
                "hosting provider",
                "subprocessor",
                "encryption at rest",
                "region",
            )
        ) or row.provider_dependency:
            return Phase2RemediationClass.CLOUD_SUBPROCESSOR

    if any(m in q for m in _SHARED_MARKERS) or "csc" in q:
        return Phase2RemediationClass.CUSTOMER_SHARED

    if any(k in q for k in _PROD_KEYWORDS) or row.implementation_state == "PRODUCTION_EVIDENCE_REQUIRED":
        return Phase2RemediationClass.PRODUCTION_EVIDENCE

    if domain in _ORG_DOMAINS or "at least annually" in q or "training" in q or "ethics committee" in q:
        return Phase2RemediationClass.ORGANIZATIONAL

    if domain in {"AIS", "IAM", "IVS", "LOG", "TVM"} or "authorization" in q or "guardrail" in q:
        if row.evidence_references and any(
            r.startswith("src/") or r.startswith("tests/") for r in row.evidence_references
        ):
            return Phase2RemediationClass.SOURCE_CODE
        return Phase2RemediationClass.RUNTIME_ARCHITECTURE

    if domain in {"CEK", "DSP"}:
        if "encrypt" in q or "key" in q:
            return Phase2RemediationClass.RUNTIME_ARCHITECTURE
        return Phase2RemediationClass.ORGANIZATIONAL

    if domain == "BCR":
        if "recover" in q or "backup" in q:
            return Phase2RemediationClass.PRODUCTION_EVIDENCE
        return Phase2RemediationClass.ORGANIZATIONAL

    if domain == "STA":
        return Phase2RemediationClass.CI_SUPPLY_CHAIN

    if row.evidence_references:
        if any(r.startswith(".github/") for r in row.evidence_references):
            return Phase2RemediationClass.CI_SUPPLY_CHAIN
        if any(r.startswith("src/") for r in row.evidence_references):
            return Phase2RemediationClass.SOURCE_CODE

    if "deploy" in q or "config" in q or "environment" in q:
        return Phase2RemediationClass.INFRA_CONFIGURATION

    return Phase2RemediationClass.OTHER_EXPLAINED


def apply_remediation_class(row: RemediationLedgerRow) -> RemediationLedgerRow:
    cls = classify_phase2_remediation(row)
    row.phase2_remediation_class = cls.value
    row.remediation_type = cls.value  # legacy column aligned
    return row
