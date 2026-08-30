"""The executor bypass invariant (WhitePact v3 authority-layer spec,
Sections 27/28/49 — one of the "mandatory" tests): `InternalToolExecutor`
must refuse to execute an action without a valid, matching, unexpired,
unconsumed `ExecutionAuthorization`, and `authorize_execution()` must
refuse to produce one for anything other than ALLOW/ALLOW_WITH_REDACTION.

Two layers proven here:
1. Unit tests against `governance/execution.py` directly — every reason
   `execute()` can refuse, in isolation.
2. `tests/test_mcp_governance_dispatch.py` (existing, unchanged by this
   file) already proves the *live* MCP dispatch path routes through
   this executor end-to-end — this file complements that with the
   tamper/bypass attempts a live protocol test can't easily construct.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorizationActionMismatchError,
    AuthorizationAlreadyConsumedError,
    AuthorizationExpiredError,
    AuthorizationOrganizationMismatchError,
    DecisionNotExecutableError,
    ExecutionAuthorization,
    GovernanceDecision,
    IdentityContext,
    InternalToolExecutor,
    authorize_execution,
)
from responsibleai.governance.models import DecisionResult
from responsibleai.governance.risk import RiskTier


def _identity(org_id: str = "org-1") -> IdentityContext:
    return IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)


def _agent(org_id: str = "org-1") -> AgentContext:
    return AgentContext(identity=_identity(org_id), organization_id=org_id, framework="mcp-client")


def _action(org_id: str = "org-1", text: str = "hello") -> ActionRequest:
    return ActionRequest(
        agent=_agent(org_id), action_type="rai_scan", target="rai_scan", arguments={"text": text}
    )


def _allow_decision(action_id: str) -> DecisionResult:
    return DecisionResult(
        decision=GovernanceDecision.ALLOW,
        action_id=action_id,
        risk_tier=RiskTier.MINIMAL,
    )


class TestAuthorizeExecutionRefusesNonExecutableDecisions:
    @pytest.mark.parametrize(
        "decision_value",
        [
            GovernanceDecision.DENY,
            GovernanceDecision.QUARANTINE,
            GovernanceDecision.REQUIRE_APPROVAL,
        ],
    )
    def test_only_allow_decisions_produce_an_authorization(self, decision_value) -> None:
        action = _action()
        decision = DecisionResult(decision=decision_value, action_id=action.action_id)
        with pytest.raises(DecisionNotExecutableError):
            authorize_execution(decision, action)

    def test_allow_and_allow_with_redaction_both_authorize(self) -> None:
        action = _action()
        for decision_value in (GovernanceDecision.ALLOW, GovernanceDecision.ALLOW_WITH_REDACTION):
            decision = DecisionResult(decision=decision_value, action_id=action.action_id)
            authorization = authorize_execution(decision, action)
            assert authorization.decision == decision_value


class TestExecutorRefusesInvalidAuthorization:
    async def test_valid_authorization_executes(self) -> None:
        action = _action()
        decision = _allow_decision(action.action_id)
        authorization = authorize_execution(decision, action)
        executor = InternalToolExecutor()
        result = await executor.execute(authorization, action)
        assert result["is_blocked"] is False  # rai_scan's real handler ran

    async def test_mismatched_action_is_refused(self) -> None:
        original = _action(text="hello")
        decision = _allow_decision(original.action_id)
        authorization = authorize_execution(decision, original)

        tampered = _action(text="totally different arguments")
        executor = InternalToolExecutor()
        with pytest.raises(AuthorizationActionMismatchError):
            await executor.execute(authorization, tampered)

    async def test_expired_authorization_is_refused(self) -> None:
        action = _action()
        decision = _allow_decision(action.action_id)
        authorization = authorize_execution(decision, action)
        # Backdate it -- expiry is checked before the digest/org checks
        # in _validate_authorization(), so a real digest/org still
        # fails here purely on expiry.
        authorization.expires_at = datetime.now(UTC) - timedelta(seconds=1)

        executor = InternalToolExecutor()
        with pytest.raises(AuthorizationExpiredError):
            await executor.execute(authorization, action)

    async def test_wrong_organization_is_refused(self) -> None:
        action = _action(org_id="org-1")
        decision = _allow_decision(action.action_id)
        authorization = authorize_execution(decision, action)

        cross_org_action = _action(org_id="org-2")
        # Same digest requires identical arguments; use the same
        # arguments but a different org's agent to isolate the org
        # check from the digest check.
        cross_org_action.arguments = action.arguments
        executor = InternalToolExecutor()
        with pytest.raises(
            (AuthorizationOrganizationMismatchError, AuthorizationActionMismatchError)
        ):
            await executor.execute(authorization, cross_org_action)

    async def test_replay_is_refused(self) -> None:
        """The core executor-bypass invariant: a second execute() call
        with the *exact* authorization that already succeeded once must
        fail — an authorization is single-use, structurally, not by
        convention."""
        action = _action()
        decision = _allow_decision(action.action_id)
        authorization = authorize_execution(decision, action)
        executor = InternalToolExecutor()

        first = await executor.execute(authorization, action)
        assert first is not None

        with pytest.raises(AuthorizationAlreadyConsumedError):
            await executor.execute(authorization, action)

    async def test_forged_authorization_with_correct_digest_still_bound_to_org(self) -> None:
        """Even if an attacker can compute the correct digest for an
        action (arguments aren't secret), they still can't manufacture
        a usable authorization without going through
        authorize_execution() -- but if they *could* construct an
        ExecutionAuthorization object directly (e.g. via a bug
        elsewhere), the org check is independent of the digest check
        and still gates it."""
        action = _action(org_id="org-1")
        from responsibleai.governance.approval import compute_action_digest

        forged = ExecutionAuthorization(
            action_digest=compute_action_digest(action),
            organization_id="org-attacker",
            decision=GovernanceDecision.ALLOW,
        )
        executor = InternalToolExecutor()
        with pytest.raises(AuthorizationOrganizationMismatchError):
            await executor.execute(forged, action)


class TestExecutionAuthorizationBindsToRedactedArguments:
    def test_authorization_digest_reflects_the_action_actually_authorized(self) -> None:
        """authorize_execution() must be called with the *final* action
        (post-redaction for ALLOW_WITH_REDACTION), not the original —
        this test locks in that contract at the unit level; the live
        redaction case is covered end-to-end in
        test_mcp_governance_dispatch.py's PII-redaction test."""
        original = _action(text="my email is alice@example.com")
        redacted = _action(text="my email is [REDACTED]")
        decision = DecisionResult(
            decision=GovernanceDecision.ALLOW_WITH_REDACTION,
            action_id=original.action_id,
            redacted_arguments={"text": "my email is [REDACTED]"},
        )
        # Authorizing against the *original* action must not match the
        # redacted one that will actually execute.
        authorization = authorize_execution(decision, original)
        assert authorization.matches_action(redacted) is False
        # Authorizing against the redacted action (what this module's
        # apply_governance() actually does) matches correctly.
        authorization2 = authorize_execution(decision, redacted)
        assert authorization2.matches_action(redacted) is True


class TestExecutionAuthorizationCarriesProvenanceFields:
    """Enterprise Readiness Phase 3 (cryptographic/structural execution
    binding): `ExecutionAuthorization` now carries `policy_version`,
    `consent_reference`, `heart_legitimacy_digest`, and `execution_id`
    -- audit/provenance binding, not independently re-validated at
    `execute()` time (see `governance/execution.py`'s own docstring for
    why these differ from `target_fingerprint`). These tests prove
    correct population and correct honest absence, not a drift check
    against a "current" value that doesn't exist for these fields."""

    def test_policy_version_is_read_from_the_decision_automatically(self) -> None:
        action = _action()
        decision = DecisionResult(
            decision=GovernanceDecision.ALLOW, action_id=action.action_id, policy_version=7
        )
        authorization = authorize_execution(decision, action)
        assert authorization.policy_version == 7

    def test_policy_version_is_none_when_no_policy_was_consulted(self) -> None:
        action = _action()
        decision = _allow_decision(action.action_id)  # policy_version defaults None
        authorization = authorize_execution(decision, action)
        assert authorization.policy_version is None

    def test_consent_reference_and_heart_digest_default_none(self) -> None:
        """The honest default: an authorization built without Heart
        having run (enterprise_mode off, or no consent_repo wired)
        must not fabricate a consent reference or legitimacy digest."""
        action = _action()
        decision = _allow_decision(action.action_id)
        authorization = authorize_execution(decision, action)
        assert authorization.consent_reference is None
        assert authorization.heart_legitimacy_digest is None

    def test_consent_reference_and_heart_digest_are_carried_through_when_supplied(self) -> None:
        action = _action()
        decision = _allow_decision(action.action_id)
        authorization = authorize_execution(
            decision,
            action,
            consent_reference="consent-abc123",
            heart_legitimacy_digest="digest-def456",
        )
        assert authorization.consent_reference == "consent-abc123"
        assert authorization.heart_legitimacy_digest == "digest-def456"

    def test_revocation_epoch_and_purpose_have_no_way_to_be_populated_yet(self) -> None:
        """Named honestly, matching governance/execution.py's own
        docstring: these fields exist on the dataclass for a future
        phase to populate, but authorize_execution() has no parameter
        for either today, since no live caller produces a value for
        them -- this test locks in that current, honest state rather
        than letting a future change silently start fabricating one."""
        action = _action()
        decision = _allow_decision(action.action_id)
        authorization = authorize_execution(decision, action)
        assert authorization.revocation_epoch is None
        assert authorization.purpose is None
        import inspect

        from responsibleai.governance.execution import authorize_execution as _fn

        assert "revocation_epoch" not in inspect.signature(_fn).parameters
        assert "purpose" not in inspect.signature(_fn).parameters

    def test_execution_id_is_distinct_from_authorization_id_and_from_other_executions(
        self,
    ) -> None:
        action = _action()
        decision = _allow_decision(action.action_id)
        auth1 = authorize_execution(decision, action)
        auth2 = authorize_execution(decision, action)
        assert auth1.execution_id != auth1.authorization_id
        assert auth1.execution_id != auth2.execution_id
