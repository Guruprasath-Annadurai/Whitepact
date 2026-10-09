# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Smallest honest runtime-authorization demonstration.

Every result comes from the existing governance APIs. A denied or
approval-gated decision never reaches an executor. This module does not
open a network connection and does not use a live secret.
"""

from __future__ import annotations

import asyncio
from typing import Any

from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    DecisionNotExecutableError,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
    authorize_execution,
)
from responsibleai.governance.authority_conflict_resolver import (
    ConflictResolutionResult,
    ConflictResolutionStatus,
)
from responsibleai.governance.authority_grant import build_authority_grant
from responsibleai.governance.authority_lattice import AuthorityEnvelope
from responsibleai.governance.evidence import build_evidence_record
from responsibleai.governance.execution import (
    AuthorizationAlreadyConsumedError,
    admit_execution,
)
from responsibleai.governance.heart_veto import apply_heart_veto
from responsibleai.governance.legitimacy_envelope import build_legitimacy_envelope
from responsibleai.sovereign.tenant import assert_same_organization
from responsibleai.sovereign.errors import SovereignTenantIsolationError


def _agent(org_id: str = "org-1") -> AgentContext:
    identity = IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)
    return AgentContext(identity=identity, framework="mcp-client", agent_id="agent-1")


def _authority(**kwargs: Any) -> AuthorityContext:
    kwargs.setdefault("delegated_by", "org-1")
    kwargs.setdefault("granted_action_types", frozenset({"mcp_tool_call"}))
    return AuthorityContext(**kwargs)


def demonstrate_denied_before_execution() -> dict[str, Any]:
    """An ungranted action is DENY, and no execution authorization is issued."""
    gateway = WhitePactRuntimeGateway()
    action = ActionRequest(agent=_agent(), action_type="payment", target="stripe")
    decision = gateway.evaluate(action, _authority())
    executed = False
    try:
        authorize_execution(decision, action)
    except DecisionNotExecutableError:
        authorization_issued = False
    else:
        authorization_issued = True
    return {
        "decision": decision.decision.value,
        "reason_codes": list(decision.reason_codes),
        "authorization_issued": authorization_issued,
        "executed": executed,
    }


def demonstrate_human_approval_required() -> dict[str, Any]:
    """A deployment the agent may attempt still stops for a human."""
    gateway = WhitePactRuntimeGateway()
    authority = _authority(
        granted_action_types=frozenset({"deployment"}),
        require_approval_for=frozenset({"deployment"}),
    )
    action = ActionRequest(agent=_agent(), action_type="deployment", target="prod")
    decision = gateway.evaluate(action, authority)
    try:
        authorize_execution(decision, action)
    except DecisionNotExecutableError:
        authorization_issued = False
    else:
        authorization_issued = True
    return {
        "decision": decision.decision.value,
        "reason_codes": list(decision.reason_codes),
        "authorization_issued": authorization_issued,
        "executed": False,
    }


def demonstrate_expired_grant_is_not_usable() -> dict[str, Any]:
    """A legitimate grant with a negative TTL cannot be treated as usable."""
    legitimacy = build_legitimacy_envelope(
        "org-1",
        "agent-1",
        apply_heart_veto(ConflictResolutionResult(ConflictResolutionStatus.LEGITIMATE)),
    )
    grant = build_authority_grant(
        "org-1",
        "user-1",
        "agent-1",
        "payment.execute",
        "vendor",
        AuthorityEnvelope(action_types=frozenset({"payment.execute"}), max_value=100.0),
        legitimacy,
        ttl_seconds=-1,
    )
    return {
        "is_legitimate": grant.is_legitimate,
        "is_expired": grant.is_expired,
        "is_usable": grant.is_usable,
        "executed": False,
    }


async def demonstrate_replay_is_refused() -> dict[str, Any]:
    """Admitting one authorization consumes it. A second admission is refused.

    ``admit_execution`` is the replay gate. This demonstration does not call
    ``InternalToolExecutor.execute``, so no tool runs.
    """
    gateway = WhitePactRuntimeGateway()
    action = ActionRequest(
        agent=_agent(),
        action_type="mcp_tool_call",
        target="rai_health",
        arguments={"query": "status"},
    )
    decision = gateway.evaluate(action, _authority())
    if decision.decision != GovernanceDecision.ALLOW:
        raise RuntimeError(f"expected ALLOW for the granted health read, got {decision.decision}")
    authorization = authorize_execution(decision, action)
    await admit_execution(authorization, action, None)
    replay_refused = False
    try:
        await admit_execution(authorization, action, None)
    except AuthorizationAlreadyConsumedError:
        replay_refused = True
    return {
        "decision": decision.decision.value,
        "first_admission_consumed": authorization.consumed,
        "replay_refused": replay_refused,
        "executed": False,
    }


def demonstrate_tenant_isolation_closed() -> dict[str, Any]:
    """A resource owned by another organization is not returned to the caller."""
    closed = False
    try:
        assert_same_organization("org-a", "org-b", resource_kind="evidence")
    except SovereignTenantIsolationError:
        closed = True
    return {"cross_tenant_closed": closed, "executed": False}


def demonstrate_evidence_omits_argument_values() -> dict[str, Any]:
    """Evidence keeps argument field names and omits the raw values."""
    gateway = WhitePactRuntimeGateway()
    secret = "super-secret-token-value"
    action = ActionRequest(
        agent=_agent(),
        action_type="payment",
        target="stripe",
        arguments={"api_token": secret},
    )
    authority = _authority()
    decision = gateway.evaluate(action, authority)
    evidence = build_evidence_record(action, action.agent, authority, decision)
    serialized = str(evidence.to_dict())
    return {
        "decision": decision.decision.value,
        "argument_keys": list(evidence.argument_keys),
        "secret_absent": secret not in serialized,
        "executed": False,
    }


def run_demo() -> dict[str, Any]:
    replay = asyncio.run(demonstrate_replay_is_refused())
    return {
        "denied_before_execution": demonstrate_denied_before_execution(),
        "human_approval_required": demonstrate_human_approval_required(),
        "expired_grant": demonstrate_expired_grant_is_not_usable(),
        "replay_refused": replay,
        "tenant_isolation": demonstrate_tenant_isolation_closed(),
        "evidence": demonstrate_evidence_omits_argument_values(),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_demo(), indent=2, sort_keys=True))
