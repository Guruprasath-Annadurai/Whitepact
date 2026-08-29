"""Tests for Enterprise Neural Phase 11 (Citadel Execution Containment).

Per `docs/enterprise-neural/11_PHASE11_DESIGN.md`: `00_PHASE0_AUDIT.md`
flagged execution-permit binding as "partially implemented... not yet
a general Citadel-style containment boundary." Since that audit,
Execution Permit v2 and the JIT Credential Broker generalized
`ExecutionAuthorization` well beyond MCP-mediated internal tool calls
to `UpstreamMCPExecutor` (target-fingerprint drift detection, per-call
narrowly-scoped credentials, DNS re-validation before dispatch) —
already real, already tested. This phase's job is to *prove* the one
property that was never regression-tested: every concrete `Executor`
implementation actually runs the shared `_validate_authorization()`
checks, so a future third executor
(`MCPExecutor`/`HTTPExecutor`, named as not-yet-built in
`execution.py`'s own docstring) can't accidentally skip or
reimplement them incorrectly -- the exact risk `Executor`'s own
docstring warns about.

Two kinds of evidence:
1. Structural regression guards: source-text scans confirming
   `_validate_authorization()` and `check_target_fingerprint()` are
   each called only from the known, audited executor implementations.
2. Runtime tests: both `InternalToolExecutor` and `UpstreamMCPExecutor`
   refuse a stale/forged authorization identically, proving the shared
   validation actually holds on both surfaces rather than assuming it
   transfers from one executor's existing tests to the other's.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from responsibleai.governance.execution import (
    AuthorizationActionMismatchError,
    AuthorizationAlreadyConsumedError,
    AuthorizationTargetDriftError,
    InternalToolExecutor,
    authorize_execution,
)
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.risk import RiskTier
from responsibleai.governance.upstream_executor import (
    ACTION_TYPE,
    UpstreamMCPExecutor,
    build_upstream_target,
)

_SRC_ROOT = Path(__file__).parent.parent / "src" / "responsibleai"

_KNOWN_EXECUTOR_FILES = {
    _SRC_ROOT / "governance" / "execution.py": "InternalToolExecutor",
    _SRC_ROOT / "governance" / "upstream_executor.py": "UpstreamMCPExecutor",
}


def _real_call_sites(function_name: str) -> list[Path]:
    """Every `.py` file under `_SRC_ROOT` containing a real call to
    `function_name` -- anchored to line-start-plus-indent so a `def`
    line or a docstring mention doesn't count. Heuristic text scan —
    see module docstring."""
    call_pattern = re.compile(rf"^\s*{re.escape(function_name)}\(", re.MULTILINE)
    hits = []
    for path in _SRC_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if call_pattern.search(path.read_text(encoding="utf-8")):
            hits.append(path)
    return hits


class TestEveryExecutorValidatesTheSharedAuthorization:
    def test_validate_authorization_call_sites_are_exactly_the_known_executors(self) -> None:
        """A source-text scan for a real call to `_validate_authorization(`
        must resolve to exactly the two known executor files -- a new
        call site would mean a third code path is (correctly or
        incorrectly) performing this validation, and the design doc's
        audit should be updated deliberately, not silently left stale."""
        hits = _real_call_sites("_validate_authorization")
        assert set(hits) == set(_KNOWN_EXECUTOR_FILES), (
            f"expected call sites {set(_KNOWN_EXECUTOR_FILES)}, found {set(hits)}"
        )


class TestCheckTargetFingerprintSingleCallSite:
    def test_check_target_fingerprint_only_called_by_upstream_executor(self) -> None:
        """`InternalToolExecutor` never sets or checks a target
        fingerprint -- internal tools have no external target to
        resolve, so a real call site appearing anywhere but
        `upstream_executor.py` would mean internal tools started being
        held to a check that doesn't apply to them, or a new executor
        added the check without understanding when it's needed."""
        hits = _real_call_sites("check_target_fingerprint")
        assert hits == [_SRC_ROOT / "governance" / "upstream_executor.py"], hits


def _identity(org_id: str = "org-1") -> IdentityContext:
    return IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)


def _agent(org_id: str = "org-1") -> AgentContext:
    return AgentContext(identity=_identity(org_id), organization_id=org_id, framework="mcp-client")


def _internal_action(org_id: str = "org-1") -> ActionRequest:
    return ActionRequest(
        agent=_agent(org_id), action_type="rai_scan", target="rai_scan", arguments={"text": "hi"}
    )


def _upstream_action(org_id: str = "org-1") -> ActionRequest:
    return ActionRequest(
        agent=_agent(org_id),
        action_type=ACTION_TYPE,
        target=build_upstream_target("srv-1", "remote_tool"),
    )


def _allow_decision(action_id: str, risk_tier: RiskTier = RiskTier.MINIMAL) -> DecisionResult:
    return DecisionResult(
        decision=GovernanceDecision.ALLOW, action_id=action_id, risk_tier=risk_tier
    )


class _FakeUpstreamRegistry:
    def __init__(self, servers: dict) -> None:
        self._servers = servers

    async def get(self, server_id: str):
        return self._servers.get(server_id)


class TestInternalToolExecutorNeverFingerprintChecks:
    async def test_no_fingerprint_authorization_executes_without_drift_error(self) -> None:
        """Runtime companion to the single-call-site guard above: a
        fresh authorization with no target_fingerprint, run through the
        real InternalToolExecutor.execute(), must never raise
        AuthorizationTargetDriftError -- proven end-to-end, not only at
        the standalone-function level."""
        action = _internal_action()
        authorization = authorize_execution(_allow_decision(action.action_id), action)
        assert authorization.target_fingerprint is None
        executor = InternalToolExecutor()
        try:
            await executor.execute(authorization, action)
        except AuthorizationTargetDriftError:
            pytest.fail("InternalToolExecutor must never raise AuthorizationTargetDriftError")


class TestSharedValidationHoldsIdenticallyOnBothExecutors:
    """Not a retest of either executor's own dedicated suite -- proves
    the four `_validate_authorization()` properties hold the same way
    on both concrete implementations, rather than assuming coverage on
    one transfers to the other."""

    async def test_replay_is_refused_on_internal_executor(self) -> None:
        action = _internal_action()
        authorization = authorize_execution(_allow_decision(action.action_id), action)
        executor = InternalToolExecutor()
        await executor.execute(authorization, action)
        with pytest.raises(AuthorizationAlreadyConsumedError):
            await executor.execute(authorization, action)

    async def test_replay_is_refused_on_upstream_executor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _fake_getaddrinfo(host, *args, **kwargs):
            return [(2, 1, 6, "", ("93.184.216.34", 0))]

        monkeypatch.setattr("responsibleai.webhooks.manager.socket.getaddrinfo", _fake_getaddrinfo)

        class _FakeServer:
            org_id = "org-1"
            url = "https://partner.example.com/mcp"
            enabled = True
            auth_token = None

        class _BoomFactory:
            def __call__(self):
                raise AssertionError("network must not be reached in this test")

        action = _upstream_action()
        authorization = authorize_execution(_allow_decision(action.action_id), action)
        executor = UpstreamMCPExecutor(
            _FakeUpstreamRegistry({"srv-1": _FakeServer()}),
            http_client_factory=_BoomFactory(),
        )
        with pytest.raises(AssertionError):
            await executor.execute(authorization, action)
        # The boom factory raised only after consumption -- the second
        # call must now hit AuthorizationAlreadyConsumedError, not the
        # boom factory again, proving replay protection holds even
        # after a downstream failure.
        with pytest.raises(AuthorizationAlreadyConsumedError):
            await executor.execute(authorization, action)

    async def test_mismatched_action_is_refused_on_internal_executor(self) -> None:
        action = _internal_action()
        authorization = authorize_execution(_allow_decision(action.action_id), action)
        tampered = ActionRequest(
            agent=action.agent,
            action_type=action.action_type,
            target=action.target,
            arguments={"text": "tampered"},
        )
        executor = InternalToolExecutor()
        with pytest.raises(AuthorizationActionMismatchError):
            await executor.execute(authorization, tampered)

    async def test_mismatched_action_is_refused_on_upstream_executor(self) -> None:
        action = _upstream_action()
        authorization = authorize_execution(_allow_decision(action.action_id), action)
        tampered = ActionRequest(
            agent=action.agent,
            action_type=action.action_type,
            target=build_upstream_target("srv-1", "different_tool"),
        )
        executor = UpstreamMCPExecutor(_FakeUpstreamRegistry({}))
        with pytest.raises(AuthorizationActionMismatchError):
            await executor.execute(authorization, tampered)
