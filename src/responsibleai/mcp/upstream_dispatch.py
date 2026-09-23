# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Wires the MCP Upstream Gateway (``governance/upstream_executor.py``)
into a REST-triggered proxied tool call — the outbound counterpart to
``governance_integration.py``'s ``apply_governance()``, which governs
this platform's own 27 in-process tools. Kept in its own module rather
than folded into ``apply_governance()``: the pre-checks are genuinely
different (org-registered external server lookup, ``ReasonCode.
UNAPPROVED_MCP_SERVER`` before the gateway is even consulted) and the
executor is different (``UpstreamMCPExecutor`` vs ``InternalToolExecutor``)
— branching one function on those differences would be harder to read
than two short ones.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository

from responsibleai.dashboard.prometheus import observe_governance_decision
from responsibleai.db import (
    ApprovalRepository,
    EvidenceRepository,
    OutcomeRepository,
    PolicyRepository,
)
from responsibleai.db.tool_trust_repository import ToolTrustRepository
from responsibleai.db.upstream_repository import UpstreamServerRepository
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
    ReasonCode,
    WhitePactRuntimeGateway,
    authorize_execution,
    format_reason,
    recent_violation_count,
)
from responsibleai.governance.approval import build_approval_request
from responsibleai.governance.authority_resolver import AuthorityDenied, AuthorityResolver
from responsibleai.governance.context import GovernanceContext
from responsibleai.governance.evidence import EvidenceRecord, build_evidence_record
from responsibleai.governance.outcome import OutcomeStatus, build_outcome_record
from responsibleai.governance.risk import classify_action_risk
from responsibleai.governance.tool_trust import ToolTrustTier, unscanned_score
from responsibleai.governance.upstream_executor import (
    ACTION_TYPE,
    UpstreamMCPExecutor,
    build_upstream_target,
    compute_upstream_target_fingerprint,
)
from responsibleai.rbac.models import OrgContext

_logger = logging.getLogger("responsibleai.mcp.upstream_gateway")


@dataclass
class UpstreamGovernanceOutcome:
    proceed: bool
    blocked_response: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    outcome_status: OutcomeStatus | None = None


async def _record_evidence(
    evidence_repo: EvidenceRepository,
    action: ActionRequest,
    agent: AgentContext,
    authority: AuthorityContext,
    decision: DecisionResult,
    *,
    authentication_method: str | None = None,
    authority_version: str | None = None,
    consent_id: str | None = None,
    consent_version: str | None = None,
    governance_epoch: int | None = None,
    execution_authorization_id: str | None = None,
    execution_nonce_reference: str | None = None,
) -> EvidenceRecord | None:
    """Same fail-closed contract as apply_governance()'s inline
    version: the persisted `EvidenceRecord` if recorded, `None` (and
    logged) on failure. Not shared as a common helper with
    governance_integration.py -- duplicating six lines is cheaper than
    coupling two independently-evolving call sites to one shared
    function for this little logic. Returns the record itself (not
    just a bool) so a caller past this point can link an
    OutcomeRecord to it via `evidence.evidence_id` (Phase 12).
    """
    evidence = build_evidence_record(
        action,
        agent,
        authority,
        decision,
        authentication_method=authentication_method,
        authority_version=authority_version,
        consent_id=consent_id,
        consent_version=consent_version,
        governance_epoch=governance_epoch,
        execution_authorization_id=execution_authorization_id,
        execution_nonce_reference=execution_nonce_reference,
    )
    try:
        await evidence_repo.record(evidence)
    except Exception:
        _logger.exception(
            "upstream_governance_evidence_write_failed action_id=%s decision=%s org_id=%s",
            action.action_id,
            decision.decision.value,
            agent.organization_id,
        )
        return None
    return evidence


async def apply_upstream_governance(
    server_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    ctx: OrgContext,
    *,
    purpose: str,
    authority_resolver: AuthorityResolver,
    gateway: WhitePactRuntimeGateway,
    evidence_repo: EvidenceRepository,
    policy_repo: PolicyRepository,
    approval_repo: ApprovalRepository,
    upstream_registry: UpstreamServerRepository,
    executor: UpstreamMCPExecutor,
    tool_trust_repo: ToolTrustRepository,
    outcome_repo: OutcomeRepository | None = None,
    epoch_repo: RevocationEpochRepository | None = None,
) -> UpstreamGovernanceOutcome:
    """Evaluate and, if governance allows it, execute one proxied call
    to an org-registered upstream MCP server. Requires an org-scoped
    *ctx* (``ctx.org_id is not None``), same requirement
    ``apply_governance()`` documents and its own callers assert.
    """
    assert ctx.org_id is not None, "apply_upstream_governance() requires an org-scoped OrgContext"
    epoch = (await epoch_repo.current(ctx.org_id)).epoch if epoch_repo is not None else None

    identity = IdentityContext(
        identity_id=ctx.key_id,
        kind="oidc" if ctx.key_id.startswith("oidc:") else "api_key",
        org_id=ctx.org_id,
        display_name=ctx.org_name,
    )
    agent = AgentContext(
        identity=identity,
        organization_id=ctx.org_id,
        agent_id=ctx.key_id,
        framework="upstream-gateway",
    )
    target = build_upstream_target(server_id, tool_name)
    action = ActionRequest(
        agent=agent,
        action_type=ACTION_TYPE,
        target=target,
        arguments=arguments,
        purpose=purpose,
    )
    # Registration IS the approval gate -- checked before the gateway
    # is even consulted, and denied with the reason code SPEC.md always
    # had reserved for exactly this case.
    server = await upstream_registry.get(server_id)
    if server is None or server.org_id != ctx.org_id or not server.enabled:
        authority = AuthorityContext(delegated_by="unresolved", granted_action_types=frozenset())
        decision = DecisionResult(
            decision=GovernanceDecision.DENY,
            action_id=action.action_id,
            reason_codes=[format_reason(ReasonCode.UNAPPROVED_MCP_SERVER, server_id=server_id)],
            risk_tier=classify_action_risk(action.action_type, action.target),
        )
        await _record_evidence(
            evidence_repo,
            action,
            agent,
            authority,
            decision,
            authentication_method=ctx.authentication_method,
            governance_epoch=epoch,
        )
        return UpstreamGovernanceOutcome(
            proceed=False,
            blocked_response={
                "error": "governance_denied",
                "message": (
                    "The named upstream MCP server is not registered, is disabled, "
                    "or belongs to a different organization."
                ),
                "action_id": decision.action_id,
                "reason_codes": decision.reason_codes,
            },
        )

    context = GovernanceContext.from_authenticated(
        ctx, action, authentication_method=ctx.authentication_method
    )
    try:
        resolved = await authority_resolver.resolve(context)
        authority = replace(
            resolved.authority,
            granted_action_types=frozenset({ACTION_TYPE}),
            require_approval_for=(
                resolved.authority.require_approval_for & frozenset({ACTION_TYPE})
            ),
        )
    except AuthorityDenied:
        authority = AuthorityContext(delegated_by="unresolved", granted_action_types=frozenset())
        decision = DecisionResult(
            decision=GovernanceDecision.DENY,
            action_id=action.action_id,
            reason_codes=[
                format_reason(ReasonCode.AUTHORITY_NOT_DELEGATED, action_type=ACTION_TYPE)
            ],
            risk_tier=classify_action_risk(action.action_type, action.target),
        )
        await _record_evidence(
            evidence_repo,
            action,
            agent,
            authority,
            decision,
            authentication_method=ctx.authentication_method,
            governance_epoch=epoch,
        )
        return UpstreamGovernanceOutcome(
            proceed=False,
            blocked_response={
                "error": "governance_denied",
                "message": "Explicit current authority and consent are required.",
                "action_id": action.action_id,
                "reason_codes": decision.reason_codes,
            },
        )

    # Tool Trust Network (Authority Everywhere Phase 8) -- the
    # destination's own trust standing, independent of who is asking.
    # Registration answers "is this server approved to exist in this
    # org's registry at all"; this answers "should calls to it keep
    # being allowed *right now*," which can change after registration
    # (a scan finds a typosquat pattern, an incident gets filed, an
    # admin revokes trust) without the registration itself changing.
    # Only BLOCKED is gated here -- TRUSTED/PROVISIONAL/UNTRUSTED all
    # still pass through to the existing risk-based decision path; see
    # governance/tool_trust.py's module docstring for why this first
    # increment stays binary rather than also modulating risk tier.
    trust_score = await tool_trust_repo.get(server_id) or unscanned_score(server_id, ctx.org_id)
    if trust_score.tier is ToolTrustTier.BLOCKED:
        decision = DecisionResult(
            decision=GovernanceDecision.DENY,
            action_id=action.action_id,
            reason_codes=[
                format_reason(
                    ReasonCode.UNTRUSTED_MCP_SERVER,
                    server_id=server_id,
                    trust_score=trust_score.score,
                )
            ],
            risk_tier=classify_action_risk(action.action_type, action.target),
        )
        await _record_evidence(
            evidence_repo,
            action,
            agent,
            authority,
            decision,
            authentication_method=ctx.authentication_method,
            authority_version=resolved.authority_version,
            consent_id=resolved.consent_id,
            consent_version=resolved.consent_version,
            governance_epoch=epoch,
        )
        return UpstreamGovernanceOutcome(
            proceed=False,
            blocked_response={
                "error": "governance_denied",
                "message": (
                    "This upstream MCP server is blocked by its current tool trust "
                    "score. Contact your org admin to review its trust standing."
                ),
                "action_id": decision.action_id,
                "reason_codes": decision.reason_codes,
            },
        )

    violation_count = await recent_violation_count(evidence_repo, ctx.org_id, agent.agent_id)
    policy = await policy_repo.get_policy(ctx.org_id)

    evaluate_started = time.monotonic()
    decision = gateway.evaluate(
        action, authority, policy=policy, recent_violation_count=violation_count
    )
    observe_governance_decision(
        decision.decision.value,
        decision.risk_tier.value if decision.risk_tier is not None else None,
        time.monotonic() - evaluate_started,
        org_id=ctx.org_id,
    )

    final_arguments = (
        decision.redacted_arguments
        if decision.decision == GovernanceDecision.ALLOW_WITH_REDACTION
        else arguments
    ) or arguments
    final_action = ActionRequest(
        agent=agent,
        action_type=ACTION_TYPE,
        target=target,
        arguments=final_arguments,
        purpose=action.purpose,
        action_id=action.action_id,
    )
    authorization = (
        authorize_execution(
            decision,
            final_action,
            target_fingerprint=compute_upstream_target_fingerprint(server),
            revocation_epoch=epoch,
        )
        if decision.decision in (GovernanceDecision.ALLOW, GovernanceDecision.ALLOW_WITH_REDACTION)
        else None
    )
    evidence = await _record_evidence(
        evidence_repo,
        action,
        agent,
        authority,
        decision,
        authentication_method=ctx.authentication_method,
        authority_version=resolved.authority_version,
        consent_id=resolved.consent_id,
        consent_version=resolved.consent_version,
        governance_epoch=epoch,
        execution_authorization_id=authorization.authorization_id if authorization else None,
        execution_nonce_reference=authorization.nonce if authorization else None,
    )
    if evidence is None:
        return UpstreamGovernanceOutcome(
            proceed=False,
            blocked_response={
                "error": "governance_evidence_unavailable",
                "message": (
                    "This action could not be evaluated because its evidence record "
                    "could not be persisted. No action was taken; retry once the "
                    "underlying issue clears."
                ),
                "action_id": decision.action_id,
            },
        )

    if decision.decision == GovernanceDecision.DENY:
        return UpstreamGovernanceOutcome(
            proceed=False,
            blocked_response={
                "error": "governance_denied",
                "message": "This action was denied by governance policy.",
                "action_id": decision.action_id,
                "reason_codes": decision.reason_codes,
            },
        )

    if decision.decision == GovernanceDecision.QUARANTINE:
        return UpstreamGovernanceOutcome(
            proceed=False,
            blocked_response={
                "error": "governance_quarantined",
                "message": (
                    "This identity is temporarily quarantined after a recent pattern "
                    "of denied actions. Contact your org admin."
                ),
                "action_id": decision.action_id,
                "reason_codes": decision.reason_codes,
            },
        )

    if decision.decision == GovernanceDecision.REQUIRE_APPROVAL:
        approval = await approval_repo.create(
            build_approval_request(
                action,
                decision,
                authentication_method=ctx.authentication_method,
                revocation_epoch=epoch,
                authority_version=resolved.authority_version,
                target_fingerprint=compute_upstream_target_fingerprint(server),
            )
        )
        return UpstreamGovernanceOutcome(
            proceed=False,
            blocked_response={
                "error": "governance_approval_required",
                "message": "This action requires human approval before it can execute.",
                "approval_id": approval.approval_id,
                "action_id": decision.action_id,
                "reason_codes": decision.reason_codes,
            },
        )

    # Execution Permit v2 -- fingerprint the server config this
    # decision was actually made against, so UpstreamMCPExecutor.execute()
    # can detect if that config drifts before the permit is consumed.
    assert authorization is not None
    try:
        result = await executor.execute(authorization, final_action)
    except Exception:
        await _record_outcome(
            outcome_repo, evidence.evidence_id, action.action_id, OutcomeStatus.UNKNOWN, ctx.org_id
        )
        raise
    status = (
        OutcomeStatus.FAILED
        if isinstance(result, dict) and result.get("is_error")
        else OutcomeStatus.SUCCEEDED
    )
    outcome_persisted = await _record_outcome(
        outcome_repo, evidence.evidence_id, action.action_id, status, ctx.org_id
    )
    return UpstreamGovernanceOutcome(
        proceed=True,
        result=result,
        outcome_status=status if outcome_persisted else OutcomeStatus.UNKNOWN,
    )


async def _record_outcome(
    outcome_repo: OutcomeRepository | None,
    evidence_id: str,
    action_id: str,
    status: OutcomeStatus,
    org_id: str | None,
) -> bool:
    """Outcome Observation (Phase 12) -- fail-open, same reasoning as
    `governance_integration.py`'s own helper of the same name: the
    proxied call has already executed by the time this runs, so a
    write failure here is a lost secondary observation, not something
    to block on. `status` uses the upstream result's own `is_error`
    field (`UpstreamMCPExecutor`'s result shape), unlike the internal-
    tool path which has no single standardized error field across all
    27 tools."""
    if outcome_repo is None:
        return False
    try:
        await outcome_repo.record(
            build_outcome_record(evidence_id, action_id, status, organization_id=org_id)
        )
        return True
    except Exception:
        _logger.exception(
            "upstream_governance_outcome_write_failed evidence_id=%s action_id=%s status=%s",
            evidence_id,
            action_id,
            status.value,
        )
        if status is not OutcomeStatus.UNKNOWN:
            try:
                await outcome_repo.record(
                    build_outcome_record(
                        evidence_id,
                        action_id,
                        OutcomeStatus.UNKNOWN,
                        organization_id=org_id,
                        result_summary="final outcome persistence failed; reconciliation required",
                    )
                )
            except Exception:
                _logger.exception(
                    "upstream_governance_unknown_outcome_write_failed evidence_id=%s action_id=%s",
                    evidence_id,
                    action_id,
                )
        return False
