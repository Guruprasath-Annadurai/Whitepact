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

A queued REQUIRE_APPROVAL now fires `WebhookEvent.APPROVAL_REQUESTED`
to any org webhook subscribed to it, via the same `WebhookManager`
class the dashboard REST API uses — `_build_http_app()` constructs and
wires its own instance when `mcp_governance_enabled` is on, since the
hosted MCP process previously had no webhook subsystem at all. What
this still does *not* cover: the self-hosted stdio transport, which
has no organizational identity to build an AuthorityContext/Policy
against and is therefore never governed by this path regardless of the
setting.

**Execution binding (v3 authority-layer work)**: an ALLOW/
ALLOW_WITH_REDACTION decision no longer just tells `_call_tool()`
"go ahead and call `dispatch_tool()` yourself" — this module now
constructs an `ExecutionAuthorization` (`governance/execution.py`) and
runs the tool itself via `InternalToolExecutor`, which structurally
cannot execute without a matching, unexpired, single-use
authorization. `_call_tool()` uses the resulting `GovernanceOutcome.result`
directly rather than calling `dispatch_tool()` a second time — there is
now exactly one place in the governed path that invokes
`dispatch_tool()`, and it's gated.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from responsibleai.dashboard.prometheus import observe_governance_decision
from responsibleai.db import (
    ApprovalRepository,
    DelegationRepository,
    EvidenceRepository,
    IntentContractRepository,
    OrgAuthorityCeilingRepository,
    OrgAutonomyBudgetRepository,
    OutcomeRepository,
    PolicyRepository,
    WorkflowRuleRepository,
)
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
    InternalToolExecutor,
    ReasonCode,
    RiskTier,
    WhitePactRuntimeGateway,
    authorize_execution,
    enrich_agent_trust_state,
    format_reason,
    recent_autonomous_action_count,
    recent_violation_count,
)
from responsibleai.governance.approval import (
    ApprovalRequest,
    build_approval_request,
    build_resume_action,
)
from responsibleai.governance.evidence import build_evidence_record
from responsibleai.governance.outcome import OutcomeStatus, build_outcome_record
from responsibleai.integrations.client import TrustClient
from responsibleai.rbac.models import OrgContext

_executor = InternalToolExecutor()

if TYPE_CHECKING:
    from responsibleai.webhooks.manager import WebhookManager

_logger = logging.getLogger("responsibleai.mcp.governance")


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
    webhook_manager: WebhookManager | None = None
    # Optional -- an org with no ceiling repo wired (or no ceiling row
    # for that org) simply never gets a `parent_authority` passed to
    # `WhitePactRuntimeGateway.evaluate()`, identical to behavior before
    # ceilings existed. Not required so existing test/deploy setups that
    # construct `GovernanceServices` without one keep working.
    ceiling_repo: OrgAuthorityCeilingRepository | None = None
    # Optional, same pattern as ceiling_repo -- an org with no rules
    # configured (or no repo wired) never gets `workflow_rules` passed
    # to `WhitePactRuntimeGateway.evaluate()`, identical to behavior
    # before the Workflow Authority Engine existed.
    workflow_rule_repo: WorkflowRuleRepository | None = None
    # Optional, same pattern -- an identity that has never been granted
    # a delegation via this graph (or no repo wired at all) is never
    # subject to the continuous re-authorization check below, identical
    # to behavior before the Delegation Graph existed.
    delegation_repo: DelegationRepository | None = None
    # Optional, same pattern -- an org with no autonomy budget
    # configured (or no repo wired) never gets an `autonomy_budget`
    # passed to `WhitePactRuntimeGateway.evaluate()`, identical to
    # behavior before the Autonomy Budget existed.
    autonomy_budget_repo: OrgAutonomyBudgetRepository | None = None
    # Optional, same pattern -- when unset, `_executor.execute()` still
    # runs exactly as before Outcome Observation existed; no
    # OutcomeRecord is ever persisted, and Reconciliation/Attestation
    # simply see "no outcome reported" for every evidence entry.
    outcome_repo: OutcomeRepository | None = None
    # Optional, same pattern -- an agent with no declared Intent
    # Contract (or no repo wired at all) never gets an `intent` passed
    # to `WhitePactRuntimeGateway.evaluate()`, identical to behavior
    # before Intent Contracts existed.
    intent_repo: IntentContractRepository | None = None


@dataclass
class GovernanceOutcome:
    proceed: bool
    arguments: dict[str, Any]
    blocked_response: dict[str, Any] | None = None
    # Set only when proceed=True — the tool already ran, via
    # InternalToolExecutor, by the time apply_governance() returns.
    # _call_tool() uses this directly instead of calling
    # dispatch_tool() itself, which is the actual enforcement: there is
    # no code path left where a governed call reaches dispatch_tool()
    # without first passing through authorize_execution().
    result: dict[str, Any] | None = None


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
        identity=identity,
        organization_id=ctx.org_id,
        agent_id=ctx.key_id,
        framework="mcp-client",
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

    # Org authority ceiling (v3 authority-layer work): a structural cap
    # no per-call authority built for this org can exceed. `ceiling` is
    # `None` for any org with no ceiling configured (or when no
    # `ceiling_repo` is wired at all) -- behavior is then identical to
    # before this feature existed.
    #
    # Value/target/depth constraints are copied directly onto the
    # per-call `authority` below, NOT left for `parent_authority` +
    # `validate_attenuation()` alone to enforce -- `constraint_violation()`
    # (the gateway's existing step 3b) is action-aware: it already knows
    # "no recognized dollar argument present -> max_value_usd doesn't
    # apply, never blocks" (see AuthorityContext's own docstring).
    # `validate_attenuation()` compares two authorities with no action in
    # scope at all, so passing the ceiling's max_value_usd *only* via
    # `parent_authority` would flag every call with no dollar argument at
    # all (e.g. `rai_health`) as an escalation, since the per-call
    # authority would have no matching constraint to compare -- a real
    # bug caught by this feature's own integration tests, not a
    # hypothetical one. Copying the constraints directly means parent and
    # child agree on this dimension by construction, and the actual
    # denial (when it fires) comes from the existing, correct,
    # action-aware VALUE_LIMIT_EXCEEDED path instead.
    #
    # `parent_authority` (below) is kept for the one thing
    # `constraint_violation()` can't check: whether `name` itself is
    # inside the ceiling's `allowed_action_types` allowlist at all.
    #
    # A ceiling-mandated approval requirement for this specific `name`
    # is folded into `require_approval_for` for the same reason as the
    # constraints above -- it should route to REQUIRE_APPROVAL (the
    # gateway's step 2), not read as this call's authority having
    # illegitimately dropped a requirement.
    ceiling = (
        await services.ceiling_repo.get(ctx.org_id) if services.ceiling_repo is not None else None
    )
    parent_authority = ceiling.to_authority_context(name) if ceiling is not None else None
    inherited_approval = (
        frozenset({name}) & ceiling.require_approval_for if ceiling is not None else frozenset()
    )
    inherited_constraints: dict[str, Any] = {}
    if ceiling is not None:
        if ceiling.max_value_usd is not None:
            inherited_constraints["max_value_usd"] = ceiling.max_value_usd
        if ceiling.allowed_targets is not None:
            inherited_constraints["allowed_targets"] = ceiling.allowed_targets
        if ceiling.denied_targets is not None:
            inherited_constraints["denied_targets"] = ceiling.denied_targets
        if ceiling.max_delegation_depth is not None:
            inherited_constraints["max_delegation_depth"] = ceiling.max_delegation_depth

    authority = AuthorityContext(
        delegated_by=ctx.org_id,
        granted_action_types=frozenset({name}),
        constraints=inherited_constraints,
        require_approval_for=inherited_approval,
    )
    action = ActionRequest(agent=agent, action_type=name, target=name, arguments=arguments)

    violation_count = await recent_violation_count(
        services.evidence_repo, ctx.org_id, agent.agent_id
    )
    policy = await services.policy_repo.get_policy(ctx.org_id)

    # Continuous re-authorization (Delegation Graph, v3 authority-layer
    # work): "authorized once != authorized forever" -- checked fresh on
    # every call, not trusted from whatever AuthorityContext was built
    # above. `latest_delegation is None` means this identity has never
    # been granted authority via this graph at all -- identical to
    # behavior before this feature existed, so it falls through to the
    # gateway's normal evaluation. A non-`None`-but-inactive delegation
    # means a previously valid grant has since expired or been revoked;
    # that's decided here, before the gateway even runs, since it's not
    # something `AuthorityContext.permits()`/`constraint_violation()`
    # (built from the ceiling/action-type grant, not this graph) can see.
    delegation_denied_reason: str | None = None
    if services.delegation_repo is not None:
        latest_delegation = await services.delegation_repo.get_latest_delegation(
            ctx.org_id, agent.agent_id
        )
        if latest_delegation is not None and not latest_delegation.is_active():
            code = (
                ReasonCode.AUTHORITY_REVOKED
                if latest_delegation.revoked_at is not None
                else ReasonCode.AUTHORITY_EXPIRED
            )
            delegation_denied_reason = format_reason(
                code, delegation_id=latest_delegation.delegation_id
            )

    # Workflow Authority Engine (v3 authority-layer work): does this
    # action, combined with the agent's own recent history, complete a
    # forbidden sequence the org has configured? Fetches the widest
    # window any of the org's rules needs in one query, then lets
    # `check_composition_violation()` apply each rule's own narrower
    # window on top -- see governance/workflow.py for why a single
    # fetched history can serve rules with different window lengths.
    workflow_rules = (
        await services.workflow_rule_repo.get_rules(ctx.org_id)
        if services.workflow_rule_repo is not None
        else []
    )
    recent_actions = []
    if workflow_rules:
        widest_window = max(rule.window_minutes for rule in workflow_rules)
        since = (datetime.now(UTC) - timedelta(minutes=widest_window)).isoformat()
        recent_actions = await services.evidence_repo.list_recent_actions(
            ctx.org_id, agent.agent_id, since=since
        )

    # Autonomy Budget (v3 authority-layer work): a rolling-window cap
    # on how many ALLOW/ALLOW_WITH_REDACTION decisions this identity
    # may accrue before the gateway forces the next one to
    # REQUIRE_APPROVAL. `autonomy_budget` is `None` for any org with no
    # budget configured (or when no `autonomy_budget_repo` is wired at
    # all) -- behavior is then identical to before this feature existed.
    autonomy_budget = (
        await services.autonomy_budget_repo.get(ctx.org_id)
        if services.autonomy_budget_repo is not None
        else None
    )
    autonomous_action_count = 0
    if autonomy_budget is not None:
        autonomous_action_count = await recent_autonomous_action_count(
            services.evidence_repo,
            ctx.org_id,
            agent.agent_id,
            window_minutes=autonomy_budget.window_minutes,
        )

    # Intent Contract (Authority Everywhere Phase 4): the goal/bounds
    # this agent itself declared for its current task, if any --
    # `None` for any agent that has never called
    # `POST /api/governance/intent-contracts` (or whose latest
    # declaration has since expired), identical to behavior before
    # this feature existed.
    intent_contract = (
        await services.intent_repo.get_active_for_agent(ctx.org_id, agent.agent_id)
        if services.intent_repo is not None
        else None
    )

    evaluate_started = time.monotonic()
    if delegation_denied_reason is not None:
        decision = DecisionResult(
            decision=GovernanceDecision.DENY,
            action_id=action.action_id,
            reason_codes=[delegation_denied_reason],
        )
    else:
        decision = services.gateway.evaluate(
            action,
            authority,
            policy=policy,
            recent_violation_count=violation_count,
            parent_authority=parent_authority,
            recent_actions=recent_actions,
            workflow_rules=workflow_rules,
            autonomy_budget=autonomy_budget,
            recent_autonomous_action_count=autonomous_action_count,
            intent=intent_contract,
        )
    observe_governance_decision(
        decision.decision.value,
        decision.risk_tier.value if decision.risk_tier is not None else None,
        time.monotonic() - evaluate_started,
        org_id=ctx.org_id,
    )
    evidence = build_evidence_record(action, agent, authority, decision)
    try:
        await services.evidence_repo.record(evidence)
    except Exception:
        # Fail closed, not open: evidence is this platform's whole audit-
        # trail guarantee (SPEC.md Section 3.7). Letting an ALLOW proceed
        # with no record of why would be a worse failure mode than
        # blocking a call during a transient DB problem — the caller can
        # retry once the underlying issue clears. Every decision branch
        # gets the same treatment here, not just ALLOW, so a QUARANTINE/
        # DENY/REQUIRE_APPROVAL outcome that also couldn't be recorded
        # doesn't get silently downgraded to "block but pretend it was
        # logged."
        _logger.exception(
            "governance_evidence_write_failed action_id=%s decision=%s org_id=%s",
            action.action_id,
            decision.decision.value,
            ctx.org_id,
        )
        return GovernanceOutcome(
            proceed=False,
            arguments=arguments,
            blocked_response={
                "error": "governance_evidence_unavailable",
                "message": (
                    "This action could not be evaluated because its evidence "
                    "record could not be persisted. No action was taken; "
                    "retry once the underlying issue clears."
                ),
                "action_id": decision.action_id,
            },
        )

    if decision.decision == GovernanceDecision.DENY:
        return GovernanceOutcome(
            proceed=False,
            arguments=arguments,
            blocked_response={
                "error": "governance_denied",
                "message": "This action was denied by governance policy.",
                "action_id": decision.action_id,
                "reason_codes": decision.reason_codes,
            },
        )

    if decision.decision == GovernanceDecision.QUARANTINE:
        return GovernanceOutcome(
            proceed=False,
            arguments=arguments,
            blocked_response={
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
            build_approval_request(action, decision),
            evidence_id=evidence.evidence_id,
            webhook_manager=services.webhook_manager,
        )
        return GovernanceOutcome(
            proceed=False,
            arguments=arguments,
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
    # The action authorized and executed must be built from
    # final_arguments, not the original `action` — for
    # ALLOW_WITH_REDACTION those differ, and the whole point of
    # binding an ExecutionAuthorization to a digest is that it binds to
    # what actually runs, not to what was originally proposed.
    final_action = ActionRequest(
        agent=agent,
        action_type=name,
        target=name,
        arguments=final_arguments,
        action_id=action.action_id,
    )
    authorization = authorize_execution(decision, final_action)
    try:
        result = await _executor.execute(authorization, final_action)
    except Exception:
        await _record_outcome(
            services,
            evidence.evidence_id,
            action.action_id,
            OutcomeStatus.ERRORED,
            organization_id=agent.organization_id,
        )
        raise
    status = (
        OutcomeStatus.FAILED
        if isinstance(result, dict) and result.get("error")
        else OutcomeStatus.SUCCEEDED
    )
    await _record_outcome(
        services,
        evidence.evidence_id,
        action.action_id,
        status,
        organization_id=agent.organization_id,
    )
    return GovernanceOutcome(proceed=True, arguments=final_arguments, result=result)


async def _record_outcome(
    services: GovernanceServices,
    evidence_id: str,
    action_id: str,
    status: OutcomeStatus,
    *,
    organization_id: str | None,
) -> None:
    """Outcome Observation (Phase 12) -- fail-open, unlike evidence
    recording above: the action has already executed by the time this
    runs, so there is nothing left to "close" on a write failure, only
    a secondary observation that didn't get recorded. Logged loudly,
    never raised, and a no-op entirely when no `outcome_repo` is wired
    (every caller before this phase existed)."""
    if services.outcome_repo is None:
        return
    try:
        await services.outcome_repo.record(
            build_outcome_record(evidence_id, action_id, status, organization_id=organization_id)
        )
    except Exception:
        _logger.exception(
            "governance_outcome_write_failed evidence_id=%s action_id=%s status=%s",
            evidence_id,
            action_id,
            status.value,
        )


def _agent_from_approval(approval: ApprovalRequest) -> AgentContext:
    """A resume flow has no live request context (no fresh OrgContext,
    no MCP call in flight) -- reconstructs the minimal `AgentContext`
    `build_resume_action()`/evidence recording need from what the
    original `ApprovalRequest` itself already recorded. `identity_id`
    falls back to `"unknown"` only for a pre-existing approval that
    somehow has no `requested_by` (shouldn't happen for anything built
    via `build_approval_request()`, which always sets it), rather than
    raising and blocking an otherwise-valid resume."""
    identity = IdentityContext(
        identity_id=approval.requested_by or "unknown",
        kind="api_key",
        org_id=approval.organization_id,
    )
    return AgentContext(
        identity=identity, organization_id=approval.organization_id, framework="resumed-approval"
    )


async def resume_approval(
    approval_id: str,
    *,
    approval_repo: ApprovalRepository,
    evidence_repo: EvidenceRepository,
    org_id: str,
    upstream_registry: Any = None,
    outcome_repo: OutcomeRepository | None = None,
) -> dict[str, Any]:
    """The REQUIRE_APPROVAL -> resume-execution pipeline: given an
    approval a human has already resolved APPROVED, reconstruct the
    exact action they approved, consume the approval (mutation/replay/
    self-approval-protected, `db/approval_repository.py`'s `consume()`),
    and actually execute it -- via `InternalToolExecutor` for one of
    this platform's own tools, or via `UpstreamMCPExecutor` when the
    persisted approval's `action_type` is
    `governance/upstream_executor.py`'s `ACTION_TYPE` (an approval
    queued by `mcp/upstream_dispatch.py`'s `apply_upstream_governance()`).
    `upstream_registry` is required only for that second case -- a
    caller that only ever resumes internal-tool approvals (the REST
    endpoint's default) can omit it and never pays for importing the
    upstream module.

    Raises `ApprovalNotFoundError`/`ApprovalNotApprovedError`/
    `ApprovalExpiredError`/`ApprovalActionMismatchError` (all from
    `db/approval_repository.py`) or `ValueError` (no persisted
    arguments, i.e. a pre-resume-feature approval, OR an upstream
    approval resumed without `upstream_registry`) -- callers (e.g. a
    REST endpoint) map these the same way the resolve endpoint already
    maps the first three.
    """
    from responsibleai.db import ApprovalNotFoundError
    from responsibleai.governance.upstream_executor import ACTION_TYPE as _UPSTREAM_ACTION_TYPE
    from responsibleai.governance.upstream_executor import UpstreamMCPExecutor

    approval = await approval_repo.get(approval_id)
    if approval is None or approval.organization_id != org_id:
        # Same 404-not-403 pattern as governance_resolve_approval: this
        # function never confirms whether an approval ID belonging to
        # another org exists.
        raise ApprovalNotFoundError(approval_id)

    agent = _agent_from_approval(approval)
    action = build_resume_action(approval, agent=agent)

    if approval.action_type == _UPSTREAM_ACTION_TYPE:
        if upstream_registry is None:
            raise ValueError(
                f"Approval {approval.approval_id!r} is an upstream MCP tool call and "
                "requires upstream_registry to resume."
            )
        executor: Any = UpstreamMCPExecutor(upstream_registry)
    else:
        executor = _executor

    # consume() is called BEFORE execution, not after -- it's the
    # single-use guard (mutation + replay protection); a resume must
    # never execute against an approval it hasn't already, atomically,
    # marked CONSUMED. If this raises, nothing below runs.
    await approval_repo.consume(approval.approval_id, action=action)

    decision = DecisionResult(
        decision=GovernanceDecision.ALLOW,
        action_id=action.action_id,
        reason_codes=[
            format_reason(ReasonCode.RESUMED_AFTER_APPROVAL, approval_id=approval.approval_id)
        ],
        risk_tier=RiskTier(approval.risk_tier) if approval.risk_tier else None,
    )
    authorization = authorize_execution(decision, action)
    result = await executor.execute(authorization, action)

    authority = AuthorityContext(
        delegated_by=org_id, granted_action_types=frozenset({action.action_type})
    )
    evidence = build_evidence_record(action, agent, authority, decision)
    evidence_recorded = True
    try:
        await evidence_repo.record(evidence)
    except Exception:
        evidence_recorded = False
        # Unlike apply_governance()'s pre-execution fail-closed
        # handling, the action has ALREADY executed by this point --
        # there's nothing left to block. Log loudly (a missing evidence
        # record for an executed action is a real audit-trail gap) but
        # still return the result; the alternative (raising here) would
        # hide a successful execution behind an unrelated DB error.
        _logger.exception(
            "resume_approval_evidence_write_failed approval_id=%s action_id=%s org_id=%s",
            approval.approval_id,
            action.action_id,
            org_id,
        )

    # Outcome Observation (Phase 12) -- only attempted when the evidence
    # write actually succeeded, so an OutcomeRecord never references a
    # non-existent evidence_id. Same fail-open reasoning as the evidence
    # write just above: the action already executed, there's nothing to
    # block on a secondary telemetry write failing.
    if evidence_recorded and outcome_repo is not None:
        status = (
            OutcomeStatus.FAILED
            if isinstance(result, dict) and result.get("error")
            else OutcomeStatus.SUCCEEDED
        )
        try:
            await outcome_repo.record(
                build_outcome_record(
                    evidence.evidence_id, action.action_id, status, organization_id=org_id
                )
            )
        except Exception:
            _logger.exception(
                "resume_approval_outcome_write_failed approval_id=%s action_id=%s",
                approval.approval_id,
                action.action_id,
            )

    return result
