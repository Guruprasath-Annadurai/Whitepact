# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Evidence-first classification for AI-CAIQ ledger rows."""

from __future__ import annotations

from scripts.csa_star_ai.ai_caiq_supplement import SUPPLEMENT
from scripts.csa_star_ai.ledger import (
    ControlAnswer,
    EvidenceStrength,
    RemediationCategory,
    RemediationLedgerRow,
)
from scripts.csa_star_ai.path_resolve import classify_paths, extract_path_tokens

# Prior CAIQ v4 evidence review — documentation-only YES must not carry forward.
_DOWNGRADE_DOC_ONLY_YES: set[str] = {
    "A&A-01.1",
    "A&A-04.1",
    "A&A-05.1",
    "A&A-06.1",
    "BCR-01.1",
    "BCR-03.1",
    "BCR-08.1",
    "BCR-08.2",
    "BCR-09.1",
    "CCC-01.1",
    "CCC-03.1",
    "CEK-03.1",
    "CEK-06.1",
    "CEK-14.1",
    "DSP-01.1",
    "DSP-08.2",
    "DSP-10.1",
    "DSP-12.1",
    "DSP-13.1",
    "DSP-19.1",
    "GRC-05.1",
    "GRC-07.1",
    "HRS-13.1",
    "IAM-12.1",
    "IAM-14.1",
    "IVS-02.1",
    "IVS-03.2",
    "IVS-09.1",
    "LOG-02.1",
    "LOG-03.1",
    "LOG-05.1",
    "LOG-09.1",
    "LOG-13.1",
    "STA-01.1",
    "STA-02.1",
}

_NA_PHYSICAL_PHRASES = (
    "physical access to the data center",
    "physical access to data centers",
    "cctv",
    "guards",
    "fire suppression",
    "datacenter security metrics",
    "data center security metrics",
    "physical media",
    "relocation or transfer of hardware",
    "business-critical equipment segregated",
    "hypervisor",
    "guest os",
)

_ANNUAL_PHRASES = (
    "at least annually",
    "reviewed and updated at least annually",
    "reviewed at least annually",
)

_DOC_ONLY_MARKERS = (
    "documented in",
    "documented process",
    "policy document",
    "runbook",
    "see governance.md",
    "see govenance",
    "informal",
    "not a formally separate",
    "not a documented multi-step",
)

_WEAK_CLAIM_MARKERS = (
    "optional mfa",
    "optional ",
    "framework mappings",
    "product feature",
    "does not prove",
    "tabletop / simulation",
    "non-production sqlite dr exercise",
    "owner assertion",
    "deployment verified",
    "provider documentation",
    "no formal",
    "not formally",
    "solo founder",
    "solo-founder",
    "pending",
    "not implemented",
)

_PROVIDER_KEYWORDS = (
    "datacenter",
    "data center",
    "physical security",
    "cctv",
    "guard",
    "fire suppression",
    "rack",
    "hypervisor",
    "physical media",
)

_ORG_KEYWORDS = (
    "background check",
    "employee termination",
    "security awareness training",
    "ethics committee",
    "law enforcement",
    "regulation authorities",
)


def _map_ownership(raw: str) -> str:
    mapping = {
        "CSP-owned": "CSP (WhitePact)",
        "CSC-owned": "CSC (customer)",
        "3rd-party outsourced": "Cloud / third-party provider",
        "Shared CSP and CSC": "Shared CSP and CSC",
        "Shared CSP and 3rd-party": "Shared CSP and third-party",
    }
    return mapping.get(raw, raw or "CSP (WhitePact)")


def _heuristic_na(question: str) -> str | None:
    q = question.casefold()
    for phrase in _NA_PHYSICAL_PHRASES:
        if phrase in q:
            return (
                "WhitePact does not operate physical datacenters or hardware logistics; "
                "control allocated to cloud provider SSRM."
            )
    return None


def _remediation_category(
    question: str, response: ControlAnswer, provider: bool, org: bool
) -> RemediationCategory:
    if response == ControlAnswer.NA or provider:
        return RemediationCategory.CLOUD_SUBPROCESSOR
    if org:
        return RemediationCategory.ORGANIZATIONAL
    q = question.casefold()
    if "customer" in q or "tenant" in q or "csc" in q:
        return RemediationCategory.CUSTOMER_SHARED
    if ".github/workflows" in q or "supply chain" in q or "sbom" in q:
        return RemediationCategory.CI_SUPPLY_CHAIN
    if response == ControlAnswer.YES:
        return RemediationCategory.SOURCE_CODE
    return RemediationCategory.UNCLASSIFIED


def _classify_from_description(
    qid: str,
    question: str,
    seed_answer: str,
    ownership: str,
    description: str,
) -> RemediationLedgerRow:
    row = RemediationLedgerRow(
        control_id=qid,
        question_id=qid,
        question=question,
    )
    desc_lower = description.casefold()
    q_lower = question.casefold()

    if seed_answer.upper() == "NA":
        row.response = ControlAnswer.NA
        row.justification = description
        row.evidence_strength = EvidenceStrength.MODERATE
        row.evidence_type = "ARCHITECTURAL_SSRM"
        row.provider_dependency = "Cloud service provider (Render, Supabase, Upstash, etc.)"
        row.ssrm_owner = ownership
        row.implementation_owner = _map_ownership(ownership)
        row.remediation_type = RemediationCategory.CLOUD_SUBPROCESSOR
        row.residual_risk = "Provider attestation and contract terms must be verified separately."
        row.status = "assessed"
        return row

    tokens = extract_path_tokens(description)
    refs, has_src, has_tests, has_workflow, compliance_doc_only = classify_paths(tokens)

    provider = any(k in q_lower for k in _PROVIDER_KEYWORDS) or ownership.startswith("3rd-party")
    org = any(k in q_lower for k in _ORG_KEYWORDS) or any(
        k in desc_lower for k in ("solo founder", "solo-founder", "ethics committee")
    )

    evidence_type = "REPOSITORY_EVIDENCE_REVIEW"
    strength = EvidenceStrength.NONE
    response = ControlAnswer.NO
    justification = description

    if qid in _DOWNGRADE_DOC_ONLY_YES or compliance_doc_only:
        response = ControlAnswer.NO
        strength = EvidenceStrength.WEAK
        justification = (
            "DOCUMENTED PROCESS / policy text only — not operational proof per "
            "compliance/CAIQ_EVIDENCE_BOUNDARY.md. " + description[:500]
        )
        evidence_type = "DOCUMENTED_PROCESS"
    elif seed_answer.upper() == "NO":
        response = ControlAnswer.NO
        strength = EvidenceStrength.NONE if "not implemented" in desc_lower else EvidenceStrength.WEAK
        justification = description
    elif has_src and has_tests:
        response = ControlAnswer.YES
        strength = EvidenceStrength.STRONG
        justification = (
            "SOURCE-CODE VERIFIED: implementation and automated tests present in repository. "
            + description[:400]
        )
    elif has_tests:
        response = ControlAnswer.YES
        strength = EvidenceStrength.MODERATE
        justification = (
            "SOURCE-CODE VERIFIED: automated tests exercise the control; "
            "implementation paths cited in test modules. "
            + description[:400]
        )
    elif has_src or has_workflow:
        response = ControlAnswer.YES
        strength = EvidenceStrength.MODERATE
        justification = (
            "SOURCE-CODE VERIFIED: implementation or CI workflow present; "
            "operating effectiveness in production not independently proven. "
            + description[:400]
        )
    elif refs:
        response = ControlAnswer.NO
        strength = EvidenceStrength.WEAK
        justification = (
            "Cited artifacts are primarily documentation or partial — insufficient for unconditional YES. "
            + description[:400]
        )
    else:
        response = ControlAnswer.NO
        strength = EvidenceStrength.NONE
        justification = description

    # Seed "Yes" without repo paths cannot be YES
    if seed_answer.upper() == "YES" and not (has_src or has_workflow or has_tests):
        response = ControlAnswer.NO
        strength = EvidenceStrength.WEAK
        justification = (
            "OWNER ASSERTION / narrative only — no verifiable repository implementation cited. "
            + description[:400]
        )
        evidence_type = "OWNER_ASSERTION_REQUIRED"

    for marker in _WEAK_CLAIM_MARKERS:
        if marker in desc_lower or marker in justification.casefold():
            if response == ControlAnswer.YES:
                response = ControlAnswer.NO
                strength = EvidenceStrength.WEAK
            break

    if any(p in q_lower for p in _ANNUAL_PHRASES) and response == ControlAnswer.YES:
        response = ControlAnswer.NO
        strength = EvidenceStrength.WEAK
        justification = (
            "Calendar-driven review/evaluation not evidenced — downgraded from optimistic mapping. "
            + description[:350]
        )
        org = True

    if response == ControlAnswer.YES and strength in {EvidenceStrength.WEAK, EvidenceStrength.NONE}:
        response = ControlAnswer.NO

    row.response = response
    row.evidence_strength = strength
    row.justification = justification
    row.evidence_references = refs
    row.evidence_type = evidence_type
    row.implementation_owner = _map_ownership(ownership)
    row.ssrm_owner = ownership
    row.implementation_description = description[:2000]
    row.partial_implementation = strength in {EvidenceStrength.WEAK, EvidenceStrength.MODERATE}
    row.provider_dependency = (
        "Cloud service provider" if provider or response == ControlAnswer.NA else ""
    )
    row.customer_responsibility = (
        "Customer configuration and data classification for shared controls."
        if "shared" in ownership.casefold()
        else ""
    )
    row.remediation_requirement = (
        "Collect provider attestation or implement in-repo control."
        if response == ControlAnswer.NO and provider
        else ("Owner sign-off required." if org else "")
    )
    row.residual_risk = (
        "Residual risk accepted pending owner/provider evidence."
        if response in {ControlAnswer.NO, ControlAnswer.NA}
        else "Technical control evidenced in repository; production config still owner-verified."
    )
    row.remediation_type = _remediation_category(question, response, provider, org)
    row.status = "assessed"
    return row


def assess_row(
    row: RemediationLedgerRow,
    hint: tuple[str, str, str] | None,
) -> RemediationLedgerRow:
    if row.response != ControlAnswer.UNASSESSED:
        return row

    na_reason = _heuristic_na(row.question)
    if na_reason:
        row.response = ControlAnswer.NA
        row.justification = na_reason
        row.evidence_strength = EvidenceStrength.MODERATE
        row.evidence_type = "ARCHITECTURAL_SSRM"
        row.provider_dependency = "Cloud service provider"
        row.remediation_type = RemediationCategory.CLOUD_SUBPROCESSOR
        row.status = "assessed"
        return row

    if hint is None:
        hint = SUPPLEMENT.get(row.question_id)

    if not hint:
        row.response = ControlAnswer.NO
        row.evidence_strength = EvidenceStrength.NONE
        row.justification = (
            "No evidence mapping for this AI-CAIQ v1.1 control ID; manual review found no defensible YES."
        )
        row.remediation_type = RemediationCategory.UNCLASSIFIED
        row.status = "assessed"
        return row

    seed_answer, ownership, description = hint
    assessed = _classify_from_description(
        row.question_id, row.question, seed_answer, ownership, description
    )
    assessed.domain = row.domain
    assessed.control_title = row.control_title
    assessed.control_specification = row.control_specification
    assessed.applicability = row.applicability
    return assessed


def second_pass_challenge(row: RemediationLedgerRow) -> RemediationLedgerRow:
    """Re-challenge every YES and NA before submission."""
    q_lower = row.question.casefold()
    j_lower = row.justification.casefold()

    if row.response == ControlAnswer.YES:
        if row.evidence_strength not in {EvidenceStrength.STRONG, EvidenceStrength.MODERATE}:
            row.response = ControlAnswer.NO
            row.changed_in_campaign = True
            row.reviewer_notes = "Second pass: YES requires STRONG/MODERATE evidence."
        elif any(m in j_lower for m in _DOC_ONLY_MARKERS):
            row.response = ControlAnswer.NO
            row.evidence_strength = EvidenceStrength.WEAK
            row.changed_in_campaign = True
            row.reviewer_notes = "Second pass: documentation-only claim rejected."
        elif "tabletop / simulation" in j_lower or "non-production sqlite dr exercise" in j_lower:
            row.response = ControlAnswer.NO
            row.evidence_strength = EvidenceStrength.WEAK
            row.changed_in_campaign = True
            row.reviewer_notes = "Second pass: exercise label is not production operational proof."
        elif any(p in q_lower for p in _ANNUAL_PHRASES):
            row.response = ControlAnswer.NO
            row.evidence_strength = EvidenceStrength.WEAK
            row.changed_in_campaign = True
            row.reviewer_notes = "Second pass: annual cadence not evidenced."

    if row.response == ControlAnswer.NA:
        if row.na_rationale or str(row.role_applicability).startswith("NOT_APPLICABLE"):
            return row
        if not any(p in q_lower for p in _NA_PHYSICAL_PHRASES) and "ssrm" not in j_lower:
            row.response = ControlAnswer.NO
            row.evidence_strength = EvidenceStrength.NONE
            row.changed_in_campaign = True
            row.reviewer_notes = "Second pass: NA requires clear SSRM/physical scope."
        elif "mfa" in q_lower or "multi-factor" in q_lower:
            row.response = ControlAnswer.NO
            row.changed_in_campaign = True
            row.reviewer_notes = "Second pass: MFA remains open until enforced with evidence."

    return row
