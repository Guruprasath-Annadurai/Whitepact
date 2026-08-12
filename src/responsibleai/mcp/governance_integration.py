"""Wires `WhitePactRuntimeGateway` into the live, hosted-MCP-transport
tool-call dispatch path — closes the gap MIGRATION_WHITEPACT_V2.md
flagged: `dispatch_tool()` used to be unchanged by any of the
governance-core work; no live MCP tool call routed through the gateway,
which only existed as a separate, opt-in REST API
(`/api/governance/*`).

Opt-in via `Settings.mcp_governance_enabled` (default `False` — see its
own docstring for why: this is a real behavior change for anyone who
enables it, not a transparent addition). Kept in its own module, not
`mcp/server.py` directly, so the self-hosted stdio transport's import
graph stays free of the DB/governance layer it never touches — `import
responsibleai.mcp.server` for `main()` (stdio) never pulls this file
in unless `_build_http_app()` actually imports it.

What this does *not* cover, stated honestly: webhook notification on a
queued REQUIRE_APPROVAL (ApprovalRepository.create()'s webhook_manager
parameter is left unset here — the hosted MCP transport has no webhook
subsystem wired in today, unlike the dashboard REST API); and the
self-hosted stdio transport, which has no organizational identity to
build an AuthorityContext/Policy against and is therefore never
governed by this path regardless of the setting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from responsibleai.db import ApprovalRepository, EvidenceRepository, PolicyRepository
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
    enrich_agent_trust_state,
    recent_violation_count,
)
from responsibleai.governance.approval import build_approval_request
from responsibleai.governance.evidence import build_evidence_record
from responsibleai.integrations.client import TrustClient
from responsibleai.rbac.models import OrgContext


@dataclass
class GovernanceServices:
    """One instance per hosted-MCP process, constructed once in
    `_build_http_app()` and threaded through the `_current_governance`
    ContextVar the same way `_current_usage_repo` already works."""

    gateway: WhitePactRuntimeGateway
    evidence_repo: EvidenceRepository
    approval_repo: ApprovalRepository
    policy_repo: PolicyRepository
    trust_client: TrustClient


@dataclass
class GovernanceOutcome:
    proceed: bool
    arguments: dict[str, Any]
    blocked_response: dict[str, Any] | None = None


async def apply_governance(
    name: str,
    arguments: dict[str, Any],
    ctx: OrgContext,
    services: GovernanceServices,
) -> GovernanceOutcome:
    """Evaluate one MCP tool call before it dispatches. Callers must
    only invoke this for an org-scoped `ctx` (``ctx.org_id is not
    None``) — a legacy flat super-admin key has no org to build
    `AuthorityContext`/persisted `Policy` against, so `_call_tool`
    skips this entirely for that case rather than erroring.

    `AgentContext.agent_id` is deliberately set to `ctx.key_id`, not
    left as the dataclass's random per-call default — quarantine
    tracking needs a *stable* identity across repeated calls from the
    same API key to accumulate a violation count against; a fresh
    random UUID every call would make `recent_violation_count()` never
    see more than zero.
    """
    assert ctx.org_id is not None, "apply_governance() requires an org-scoped OrgContext"

    identity = IdentityContext(
        identity_id=ctx.key_id,
        kind="oidc" if ctx.key_id.startswith("oidc:") else "api_key",
        org_id=ctx.org_id,
        display_name=ctx.org_name,
    )
    agent = AgentContext(
        identity=identity, organization_id=ctx.org_id, agent_id=ctx.key_id, framework="mcp-client",
    )

    # Several rai_* tools accept `provider`/`model` arguments naming the
    # third-party model the call is *about* — when present, that's a
    # real signal for a Trust Index lookup, unlike the MCP protocol's
    # own tool-call envelope, which carries no such field.
    provider = arguments.get("provider")
    model = arguments.get("model")
    if isinstance(provider, str) and isinstance(model, str):
        agent.provider = provider
        agent.model = model
        agent = await enrich_agent_trust_state(agent, services.trust_client)

    authority = AuthorityContext(delegated_by=ctx.org_id, granted_action_types=frozenset({name}))
    action = ActionRequest(agent=agent, action_type=name, target=name, arguments=arguments)

    violation_count = await recent_violation_count(services.evidence_repo, ctx.org_id, agent.agent_id)
    policy = await services.policy_repo.get_policy(ctx.org_id)

    decision = services.gateway.evaluate(
        action, authority, policy=policy, recent_violation_count=violation_count,
    )
    evidence = build_evidence_record(action, agent, authority, decision)
    await services.evidence_repo.record(evidence)

    if decision.decision == GovernanceDecision.DENY:
        return GovernanceOutcome(
            proceed=False, arguments=arguments, blocked_response={
                "error": "governance_denied",
                "message": "This action was denied by governance policy.",
                "action_id": decision.action_id,
                "reason_codes": decision.reason_codes,
            },
        )

    if decision.decision == GovernanceDecision.QUARANTINE:
        return GovernanceOutcome(
            proceed=False, arguments=arguments, blocked_response={
                "error": "governance_quarantined",
                "message": (
                    "This identity is temporarily quarantined after a recent "
                    "pattern of denied actions. Contact your org admin."
                ),
                "action_id": decision.action_id,
                "reason_codes": decision.reason_codes,
            },
        )

    if decision.decision == GovernanceDecision.REQUIRE_APPROVAL:
        approval = await services.approval_repo.create(
            build_approval_request(action, decision), evidence_id=evidence.evidence_id,
        )
        return GovernanceOutcome(
            proceed=False, arguments=arguments, blocked_response={
                "error": "governance_approval_required",
                "message": "This action requires human approval before it can execute.",
                "approval_id": approval.approval_id,
                "action_id": decision.action_id,
                "reason_codes": decision.reason_codes,
            },
        )

    if decision.decision == GovernanceDecision.ALLOW_WITH_REDACTION:
        return GovernanceOutcome(proceed=True, arguments=decision.redacted_arguments or arguments)

    return GovernanceOutcome(proceed=True, arguments=arguments)
