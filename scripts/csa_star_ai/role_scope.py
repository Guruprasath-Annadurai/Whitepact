# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Architecture-based CSA role and applicability analysis per AI-CAIQ row."""

from __future__ import annotations

from dataclasses import dataclass, field

from scripts.csa_star_ai.ledger import RemediationLedgerRow
from scripts.csa_star_ai.phase2_categories import CSARole, ImplementationState

_SCOPE_DOC = "compliance/csa-star-ai/WHITEPACT_SERVICE_SCOPE.md"
_ARCH_EVIDENCE = [
    "src/responsibleai/runtime/authority_kernel.py",
    "src/responsibleai/mcp/upstream_dispatch.py",
    "compliance/csa-star-ai/WHITEPACT_SERVICE_SCOPE.md",
]

_PHYSICAL_PHRASES = (
    "physical access to the data center",
    "physical access to data centers",
    "cctv",
    "guards",
    "fire suppression",
    "physical media",
    "relocation or transfer of hardware",
    "business-critical equipment segregated",
    "datacenter security metrics",
    "data center security metrics",
    "environmental risk",
    "power and environmental",
    "hypervisor",
    "guest os",
    "secure transportation of physical",
)

_VENDOR_ASSURANCE_DCS = (
    "dcs-01",
    "dcs-02",
    "dcs-04",
    "dcs-06",
    "dcs-07",
    "dcs-08",
    "dcs-09",
    "dcs-10",
    "dcs-11",
    "dcs-12",
    "dcs-13",
    "dcs-14",
    "dcs-15",
)

# MDS rows where WhitePact may have OSP/AP integration duty (not full MP pipeline)
_MDS_SHARED_INTEGRATION = {"MDS-11.1", "MDS-12.1"}


@dataclass
class RoleContext:
    primary_role: CSARole = CSARole.OSP
    secondary_roles: list[CSARole] = field(default_factory=lambda: [CSARole.AP])
    excluded_roles: list[CSARole] = field(default_factory=lambda: [CSARole.MP, CSARole.CSP])
    whitepact_responsibility: str = ""
    provider_responsibility: str = ""
    customer_responsibility: str = ""
    shared_responsibility: str = ""
    role_applicability: str = "APPLICABLE"
    na_eligible: bool = False
    na_rationale: str = ""
    scope_basis: str = ""
    scope_evidence: list[str] = field(default_factory=list)
    implementation_state: ImplementationState = ImplementationState.MISSING
    role_reasoning: str = ""


def _q(row: RemediationLedgerRow) -> str:
    return (row.question or "").casefold()


def _domain(row: RemediationLedgerRow) -> str:
    if row.domain:
        return row.domain.upper()
    qid = row.question_id or row.control_id
    return qid.split("-", 1)[0] if "-" in qid else ""


def analyze_role(row: RemediationLedgerRow) -> RoleContext:
    ctx = RoleContext(
        primary_role=CSARole.OSP,
        secondary_roles=[CSARole.AP],
        excluded_roles=[CSARole.MP, CSARole.CSP],
        whitepact_responsibility=(
            "Governance runtime: identity, authority kernel, policy enforcement, "
            "approvals, controlled egress, audit metadata, revocation."
        ),
        provider_responsibility=(
            "Underlying cloud/hosting (compute, storage, network, physical DC) per SUBPROCESSOR_REGISTER."
        ),
        customer_responsibility=(
            "Customer LLM/model provider choice, prompts/data classification, IdP, deployment config."
        ),
        scope_evidence=list(_ARCH_EVIDENCE),
        scope_basis=_SCOPE_DOC,
    )
    q = _q(row)
    domain = _domain(row)
    qid = row.question_id

    ctx.role_reasoning = (
        f"WhitePact verified as OSP/AP (not MP/CSP): independent authorization layer; "
        f"domain={domain}; see {_SCOPE_DOC}."
    )

    # --- Physical / hypervisor → NA when operation is provider-only ---
    if any(p in q for p in _PHYSICAL_PHRASES):
        ctx.na_eligible = True
        ctx.role_applicability = "NOT_APPLICABLE_PHYSICAL_SSRM"
        ctx.na_rationale = (
            "NA_RATIONALE: control targets physical datacenter/media/hypervisor operations. "
            "WhitePact does not operate physical infrastructure; cloud provider SSRM. "
            "Customer may verify provider attestations separately (vendor assurance, not operator)."
        )
        ctx.implementation_state = ImplementationState.OUT_OF_SCOPE
        ctx.provider_responsibility = "Cloud/hosting provider operates physical and hypervisor layers."
        return ctx

    # --- DCS vendor assurance (not operator) ---
    if domain == "DCS" and qid not in {"DCS-03.1", "DCS-03.3", "DCS-05.1", "DCS-05.2", "DCS-16.1", "DCS-17.1", "DCS-18.1"}:
        prefix = qid.split(".")[0].casefold()
        if any(prefix == p for p in _VENDOR_ASSURANCE_DCS) or "data center" in q or "datacenter" in q:
            ctx.role_applicability = "APPLICABLE_VENDOR_ASSURANCE"
            ctx.implementation_state = ImplementationState.PROVIDER_DEPENDENT
            ctx.whitepact_responsibility = (
                "Subprocessor due diligence and contract review — not operating the datacenter."
            )
            ctx.na_eligible = False
            return ctx

    # --- MDS per-control (not blanket NA) ---
    if domain == "MDS" or qid.startswith("MDS"):
        if qid in _MDS_SHARED_INTEGRATION:
            ctx.role_applicability = "APPLICABLE_SHARED"
            ctx.shared_responsibility = (
                "Customer/model provider owns model artifacts; WhitePact evaluates runtime/orchestration risk."
            )
            ctx.implementation_state = ImplementationState.PARTIAL
            ctx.na_eligible = False
            return ctx
        if "training" in q or "fine-tun" in q or "checkpoint" in q or "sign" in q and "model" in q:
            ctx.na_eligible = True
            ctx.role_applicability = "NOT_APPLICABLE_MP_SCOPE"
            ctx.na_rationale = (
                "NA_RATIONALE: Model Development Security for training/signing/checkpoint pipelines. "
                "WhitePact does not train, fine-tune, sign, or host proprietary model weights (OSP/AP only). "
                "Upstream Model Provider / customer owns MP obligations."
            )
            ctx.implementation_state = ImplementationState.OUT_OF_SCOPE
            ctx.provider_responsibility = "Customer-chosen model provider (MP) or customer ML ops."
            return ctx
        # Default MDS: artifact scanning, documentation lifecycle, serialization
        ctx.na_eligible = True
        ctx.role_applicability = "NOT_APPLICABLE_MP_SCOPE"
        ctx.na_rationale = (
            "NA_RATIONALE: MDS control assumes WhitePact develops/deploys model artifacts. "
            "Repository review shows governance/orchestration only — no model-development pipeline."
        )
        ctx.implementation_state = ImplementationState.OUT_OF_SCOPE
        return ctx

    # --- Customer LLM / tenant data ---
    if "customer" in q and "tenant" not in q and domain in {"DSP", "IPY"}:
        ctx.shared_responsibility = "Customer data classification and upstream model policies."
        ctx.implementation_state = ImplementationState.CUSTOMER_SHARED

    # --- Logging content (LOG-15/16) ---
    if qid in {"LOG-15.1", "LOG-16.1"}:
        ctx.role_applicability = "APPLICABLE"
        ctx.implementation_state = ImplementationState.PARTIAL
        ctx.whitepact_responsibility = (
            "Metadata/decision audit without retaining full prompt/completion bodies (privacy posture)."
        )
        ctx.na_eligible = False

    return ctx


def apply_role_to_row(row: RemediationLedgerRow) -> RemediationLedgerRow:
    ctx = analyze_role(row)
    row.primary_role = ctx.primary_role.value
    row.secondary_roles = [r.value for r in ctx.secondary_roles]
    row.role_applicability = ctx.role_applicability
    row.whitepact_responsibility = ctx.whitepact_responsibility
    row.provider_responsibility = ctx.provider_responsibility
    row.customer_responsibility = ctx.customer_responsibility or row.customer_responsibility
    row.shared_responsibility = ctx.shared_responsibility
    row.na_candidate = ctx.na_eligible
    row.na_rationale = ctx.na_rationale
    row.scope_basis = ctx.scope_basis
    row.scope_evidence = ctx.scope_evidence
    row.implementation_state = ctx.implementation_state.value
    row.role_reasoning = ctx.role_reasoning
    return row
