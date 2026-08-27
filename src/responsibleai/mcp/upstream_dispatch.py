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
from dataclasses import dataclass
from typing import Any

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


async def _record_evidence(
    evidence_repo: EvidenceRepository,
    action: ActionRequest,
    agent: AgentContext,
    authority: AuthorityContext,
    decision: DecisionResult,
    *,
    authority_grant_digest: str | None = None,
    legitimacy_digest: str | None = None,
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
        authority_grant_digest=authority_grant_digest,
        legitimacy_digest=legitimacy_digest,
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
    gateway: WhitePactRuntimeGateway,
    evidence_repo: EvidenceRepository,
    policy_repo: PolicyRepository,
    approval_repo: ApprovalRepository,
    upstream_registry: UpstreamServerRepository,
    executor: UpstreamMCPExecutor,
    tool_trust_repo: ToolTrustRepository,
    outcome_repo: OutcomeRepository | None = None,
    authority_resolver: Any = None,
    heart_enforcement_required: bool = False,
) -> UpstreamGovernanceOutcome:
    """Evaluate and, if governance allows it, execute one proxied call
    to an org-registered upstream MCP server. Requires an org-scoped
    *ctx* (``ctx.org_id is not None``), same requirement
    ``apply_governance()`` documents and its own callers assert.
    """
    assert ctx.org_id is not None, "apply_upstream_governance() requires an org-scoped OrgContext"

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
    action = ActionRequest(agent=agent, action_type=ACTION_TYPE, target=target, arguments=arguments)
    authority = AuthorityContext(
        delegated_by=ctx.org_id, granted_action_types=frozenset({ACTION_TYPE})
    )
    grant = None

    # Registration IS the approval gate -- checked before the gateway
    # is even consulted, and denied with the reason code SPEC.md always
    # had reserved for exactly this case.
    server = await upstream_registry.get_for_org(ctx.org_id, server_id)
    if server is None or not server.enabled:
        decision = DecisionResult(
            decision=GovernanceDecision.DENY,
            action_id=action.action_id,
            reason_codes=[format_reason(ReasonCode.UNAPPROVED_MCP_SERVER, server_id=server_id)],
            risk_tier=classify_action_risk(action.action_type, action.target),
        )
        await _record_evidence(evidence_repo, action, agent, authority, decision)
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
        await _record_evidence(evidence_repo, action, agent, authority, decision)
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

    authority_resolution_denied_reason: str | None = None
    if authority_resolver is not None:
        from responsibleai.governance.authority_resolver import AuthorityResolutionError

        requested_purpose = arguments.get("purpose")
        try:
            grant = await authority_resolver.resolve(
                identity,
                action_type=ACTION_TYPE,
                target=target,
                purpose=requested_purpose if isinstance(requested_purpose, str) else None,
            )
            authority = grant.to_authority_context()
        except AuthorityResolutionError as exc:
            authority_resolution_denied_reason = str(exc)
            authority = AuthorityContext(delegated_by=ctx.org_id, granted_action_types=frozenset())
    elif heart_enforcement_required:
        authority_resolution_denied_reason = (
            "HEART_RESOLVER_UNAVAILABLE: production Heart enforcement has no resolver"
        )
        authority = AuthorityContext(delegated_by=ctx.org_id, granted_action_types=frozenset())

    evaluate_started = time.monotonic()
    if authority_resolution_denied_reason is not None:
        decision = DecisionResult(
            decision=GovernanceDecision.DENY,
            action_id=action.action_id,
            reason_codes=[authority_resolution_denied_reason],
        )
    else:
        decision = gateway.evaluate(
            action, authority, policy=policy, recent_violation_count=violation_count
        )
    observe_governance_decision(
        decision.decision.value,
        decision.risk_tier.value if decision.risk_tier is not None else None,
        time.monotonic() - evaluate_started,
        org_id=ctx.org_id,
    )

    evidence = await _record_evidence(
        evidence_repo,
        action,
        agent,
        authority,
        decision,
        authority_grant_digest=grant.canonical_digest if grant is not None else None,
        legitimacy_digest=(grant.legitimacy.canonical_digest if grant is not None else None),
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
        approval = await approval_repo.create(build_approval_request(action, decision))
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

    final_arguments = (
        decision.redacted_arguments
        if decision.decision == GovernanceDecision.ALLOW_WITH_REDACTION
        else arguments
    )
    final_arguments = final_arguments or arguments
    final_action = ActionRequest(
        agent=agent,
        action_type=ACTION_TYPE,
        target=target,
        arguments=final_arguments,
        action_id=action.action_id,
    )
    # Execution Permit v2 -- fingerprint the server config this
    # decision was actually made against, so UpstreamMCPExecutor.execute()
    # can detect if that config drifts before the permit is consumed.
    authorization = authorize_execution(
        decision,
        final_action,
        target_fingerprint=compute_upstream_target_fingerprint(server),
        authority_grant=grant,
        require_heart=heart_enforcement_required,
    )
    try:
        result = await executor.execute(authorization, final_action)
    except Exception:
        await _record_outcome(
            outcome_repo, evidence.evidence_id, action.action_id, OutcomeStatus.ERRORED, ctx.org_id
        )
        raise
    status = (
        OutcomeStatus.FAILED
        if isinstance(result, dict) and result.get("is_error")
        else OutcomeStatus.SUCCEEDED
    )
    await _record_outcome(outcome_repo, evidence.evidence_id, action.action_id, status, ctx.org_id)
    return UpstreamGovernanceOutcome(proceed=True, result=result)


async def _record_outcome(
    outcome_repo: OutcomeRepository | None,
    evidence_id: str,
    action_id: str,
    status: OutcomeStatus,
    org_id: str | None,
) -> None:
    """Outcome Observation (Phase 12) -- fail-open, same reasoning as
    `governance_integration.py`'s own helper of the same name: the
    proxied call has already executed by the time this runs, so a
    write failure here is a lost secondary observation, not something
    to block on. `status` uses the upstream result's own `is_error`
    field (`UpstreamMCPExecutor`'s result shape), unlike the internal-
    tool path which has no single standardized error field across all
    27 tools."""
    if outcome_repo is None:
        return
    try:
        await outcome_repo.record(
            build_outcome_record(evidence_id, action_id, status, organization_id=org_id)
        )
    except Exception:
        _logger.exception(
            "upstream_governance_outcome_write_failed evidence_id=%s action_id=%s status=%s",
            evidence_id,
            action_id,
            status.value,
        )
