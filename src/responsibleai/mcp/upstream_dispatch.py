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
from responsibleai.db import ApprovalRepository, EvidenceRepository, PolicyRepository
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
from responsibleai.governance.evidence import build_evidence_record
from responsibleai.governance.risk import classify_action_risk
from responsibleai.governance.upstream_executor import (
    ACTION_TYPE,
    UpstreamMCPExecutor,
    build_upstream_target,
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
) -> bool:
    """Same fail-closed contract as apply_governance()'s inline
    version: True if recorded, False (and logged) on failure. Not
    shared as a common helper with governance_integration.py --
    duplicating six lines is cheaper than coupling two independently-
    evolving call sites to one shared function for this little logic.
    """
    evidence = build_evidence_record(action, agent, authority, decision)
    try:
        await evidence_repo.record(evidence)
    except Exception:
        _logger.exception(
            "upstream_governance_evidence_write_failed action_id=%s decision=%s org_id=%s",
            action.action_id,
            decision.decision.value,
            agent.organization_id,
        )
        return False
    return True


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

    # Registration IS the approval gate -- checked before the gateway
    # is even consulted, and denied with the reason code SPEC.md always
    # had reserved for exactly this case.
    server = await upstream_registry.get(server_id)
    if server is None or server.org_id != ctx.org_id or not server.enabled:
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

    if not await _record_evidence(evidence_repo, action, agent, authority, decision):
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
    authorization = authorize_execution(decision, final_action)
    result = await executor.execute(authorization, final_action)
    return UpstreamGovernanceOutcome(proceed=True, result=result)
