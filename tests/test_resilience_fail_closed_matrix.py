"""Tests for Enterprise Neural Phase 14 (Resilience + Fail-Closed
Operations).

Per `docs/enterprise-neural/14_PHASE14_DESIGN.md`: `THREAT_MODEL.md`
already documents two deliberately asymmetric cases — evidence-write
failures fail *closed* (explicit try/except,
`tests/test_mcp_governance_dispatch.py::TestEvidenceWriteFailsClosed`);
Trust Index lookups fail *open* (by design). A third case,
`WhitePactRuntimeGateway.evaluate()` crashing, is already proven to
fail closed by simple exception propagation
(`TestAuthoritySubsystemCrashFailsClosed` in that same file) — no
try/except wraps it; an exception structurally prevents evidence being
written or the executor being reached at all.

`apply_governance()` calls six more repository dependencies before
`evaluate()` — `ceiling_repo`, `policy_repo`, `delegation_repo`,
`workflow_rule_repo`, `autonomy_budget_repo`, `intent_repo` — none
individually wrapped in a try/except either, relying on the identical
propagation mechanism. This file generalizes
`TestAuthoritySubsystemCrashFailsClosed`'s exact pattern across all
six, so the matrix is regression-tested dependency-by-dependency
rather than assumed to transfer from the one dependency
(`gateway.evaluate()`) that already had a test.

**Security Remediation Gap 6** extends this same matrix with four more
cells the remediation directive names, reproduced first (see
`docs/enterprise-neural/REMEDIATION_GAP6_FAIL_CLOSED_MATRIX.md`):
policy-engine (`Policy.evaluate()` itself raising, distinct from its
repository lookup already covered above), an individual tool crashing
mid-execution, a network timeout to an upstream MCP server, and a
field-encryption key mismatch after rotation. Every one of these four
turned out to be an already-correct fail-closed code path with no
prior test under this exact name — this file closes that testing gap,
it does not change any of the four behaviors.
"""

from __future__ import annotations

import json

import pytest
from asgi_lifespan import LifespanManager

from responsibleai.db import (
    DelegationRepository,
    EvidenceRepository,
    IntentContractRepository,
    OrgAuthorityCeilingRepository,
    OrgAutonomyBudgetRepository,
    OrgRepository,
    PolicyRepository,
    WorkflowRuleRepository,
    create_engine,
)
from responsibleai.rbac.models import Plan, Role


@pytest.fixture()
async def governed_app(monkeypatch: pytest.MonkeyPatch):
    """Identical to `test_mcp_governance_dispatch.py`'s own fixture of
    the same name -- duplicated, not imported, so this phase's
    contribution stays a single, independently deletable file (see
    every prior phase's own "Rollback procedure" convention)."""
    import responsibleai.db as db_module
    from responsibleai.dashboard.config import get_settings
    from responsibleai.mcp.server import _build_http_app

    settings = get_settings()
    monkeypatch.setattr(settings, "mcp_governance_enabled", True)

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)

    org_repo = OrgRepository(engine)
    org = await org_repo.create_org("Governed Co", "governed-co", plan=Plan.ENTERPRISE)
    _key_rec, raw_key = await org_repo.create_key(org.id, "test-key", role=Role.ANALYST)

    app = _build_http_app()
    async with LifespanManager(app) as manager:
        yield manager.app, raw_key, org.id, engine

    await engine.close()


async def _call(app, raw_key: str, tool_name: str, arguments: dict):
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            headers={"Authorization": f"Bearer {raw_key}"},
        ) as http_client,
        streamable_http_client("/mcp", http_client=http_client) as (
            read_stream,
            write_stream,
            _get_session_id,
        ),
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments)


def _raise(*_args, **_kwargs):
    raise RuntimeError("simulated dependency crash")


class TestPreEvaluateDependencyCrashesFailClosed:
    """Generalizes TestAuthoritySubsystemCrashFailsClosed
    (test_mcp_governance_dispatch.py) across every repository
    dependency apply_governance() calls before gateway.evaluate() --
    same invariant, same double-check (no real payload, no fabricated
    evidence), proven independently for each rather than assumed to
    transfer from the one dependency already covered."""

    @pytest.mark.parametrize(
        ("repo_class", "method_name"),
        [
            (OrgAuthorityCeilingRepository, "get"),
            (PolicyRepository, "get_policy"),
            (DelegationRepository, "get_latest_delegation"),
            (WorkflowRuleRepository, "get_rules"),
            (OrgAutonomyBudgetRepository, "get"),
            (IntentContractRepository, "get_active_for_agent"),
        ],
    )
    async def test_dependency_crash_never_executes_the_tool(
        self,
        governed_app,
        monkeypatch: pytest.MonkeyPatch,
        repo_class: type,
        method_name: str,
    ) -> None:
        monkeypatch.setattr(repo_class, method_name, _raise)

        app, raw_key, org_id, engine = governed_app
        try:
            result = await _call(app, raw_key, "rai_health", {})
        except Exception:  # noqa: BLE001 -- either failure mode proves fail-closed
            pass
        else:
            assert result.isError is True or "status" not in json.loads(result.content[0].text)

        records = await EvidenceRepository(engine).list_for_org(org_id)
        assert not any(r.action_type == "rai_health" for r in records)


class TestPolicyEngineCrashFailsClosed:
    """Distinct from `PolicyRepository.get_policy` crashing (already
    covered above, at the DB-lookup layer) -- this proves the policy
    *engine itself*, `Policy.evaluate()`, raising also fails closed.
    `PolicyRepository.get_policy()` always returns a real `Policy`
    instance (empty rules if none configured, never `None` --
    `db/policy_repository.py`'s own docstring), so `policy.evaluate()`
    genuinely runs on every governed call today; no rule needs to be
    configured first for this crash to be reachable."""

    async def test_policy_evaluate_crash_never_executes_the_tool(
        self,
        governed_app,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from responsibleai.governance.policy import Policy

        monkeypatch.setattr(Policy, "evaluate", _raise)

        app, raw_key, org_id, engine = governed_app
        try:
            result = await _call(app, raw_key, "rai_health", {})
        except Exception:  # noqa: BLE001 -- either failure mode proves fail-closed
            pass
        else:
            assert result.isError is True or "status" not in json.loads(result.content[0].text)

        records = await EvidenceRepository(engine).list_for_org(org_id)
        assert not any(r.action_type == "rai_health" for r in records)


class TestIndividualToolCrashFailsClosed:
    """A governed call whose *decision* is ALLOW but whose underlying
    tool implementation crashes during execution --
    `mcp/governance_integration.py`'s `try/except Exception:
    ...outcome=ERRORED...; raise` around `_executor.execute()`. Unlike
    the pre-`evaluate()` crashes above, evidence for this action DOES
    exist (it was written before dispatch, per the fail-closed
    pre-execution evidence check) -- the invariant here is narrower and
    just as important: no fabricated success payload is ever returned
    for a tool that never actually completed."""

    async def test_tool_crash_never_returns_a_fabricated_success(
        self,
        governed_app,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import responsibleai.mcp.tools as tools_module

        async def _raise_tool_crash(*_args, **_kwargs):
            raise RuntimeError("simulated tool implementation crash")

        monkeypatch.setattr(tools_module, "dispatch_tool", _raise_tool_crash)

        app, raw_key, _org_id, _engine = governed_app
        try:
            result = await _call(app, raw_key, "rai_health", {})
        except Exception:  # noqa: BLE001 -- either failure mode proves fail-closed
            pass
        else:
            assert result.isError is True or "status" not in json.loads(result.content[0].text)


class TestUpstreamNetworkTimeoutFailsClosed:
    """A proxied call to a registered external MCP server whose network
    connection times out. `UpstreamMCPExecutor.execute()`
    (`governance/upstream_executor.py`) has no try/except around the
    actual outbound call -- a timeout (or any other network failure)
    propagates exactly like the individual-tool crash above."""

    async def test_network_timeout_propagates_rather_than_returning_a_fake_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import httpx

        def _fake_getaddrinfo(host, *args, **kwargs):
            return [(2, 1, 6, "", ("93.184.216.34", 0))]

        monkeypatch.setattr("responsibleai.webhooks.manager.socket.getaddrinfo", _fake_getaddrinfo)

        from responsibleai.governance.execution import authorize_execution
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

        class _FakeRegistry:
            def __init__(self, servers: dict) -> None:
                self._servers = servers

            async def get(self, server_id: str):
                return self._servers.get(server_id)

        class _FakeServer:
            def __init__(self, org_id: str, url: str) -> None:
                self.org_id = org_id
                self.url = url
                self.enabled = True
                self.auth_token = None

        def _timing_out_http_client_factory():
            raise httpx.TimeoutException("simulated network timeout")

        registry = _FakeRegistry({"srv-1": _FakeServer("org-1", "https://partner.example.com/mcp")})
        identity = IdentityContext(identity_id="k1", kind="api_key", org_id="org-1")
        agent = AgentContext(
            identity=identity, organization_id="org-1", framework="upstream-gateway"
        )
        action = ActionRequest(
            agent=agent, action_type=ACTION_TYPE, target=build_upstream_target("srv-1", "tool_a")
        )
        decision = DecisionResult(
            decision=GovernanceDecision.ALLOW, action_id=action.action_id, risk_tier=RiskTier.HIGH
        )
        authorization = authorize_execution(decision, action)

        executor = UpstreamMCPExecutor(
            registry, http_client_factory=_timing_out_http_client_factory
        )
        with pytest.raises(httpx.TimeoutException):
            await executor.execute(authorization, action)


class TestKeyRotationMidRequestFailsClosed:
    """`EncryptedString.process_result_value()`
    (`db/encryption.py`) decrypts using whatever field-encryption key is
    *currently* active (a process-global cache set by
    `configure_field_encryption_key()`), not by resolving whichever key
    version a given ciphertext was actually encrypted under. This
    proves the resulting behavior after a rotation is fail-closed, not
    fail-open: a value encrypted under the pre-rotation key, read after
    the active key changes, must raise `DecryptionError` -- never
    silently return wrong or corrupted plaintext.
    `governance/crypto/envelope.py`'s `decrypt_envelope()` is what
    actually enforces this (embedded `KeyId` must match the expected
    one); this test proves the enforcement reaches all the way through
    the SQLAlchemy column type, not just the lower-level primitive
    `test_crypto_activation.py` already covers."""

    async def test_ciphertext_from_the_pre_rotation_key_fails_closed_after_rotation(
        self,
    ) -> None:
        import os

        from responsibleai.db.encryption import (
            EncryptedString,
            clear_field_encryption_key,
            configure_field_encryption_key,
        )
        from responsibleai.governance.crypto.types import DecryptionError, KeyId, KeyPurpose

        column = EncryptedString()
        try:
            key_v1 = KeyId(
                purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id=None, version=1, environment="test"
            )
            configure_field_encryption_key(key_v1, os.urandom(32))
            ciphertext = column.process_bind_param("sensitive-value", dialect=None)

            # Simulate rotation: a new key becomes active mid-deployment,
            # before this ciphertext has been re-encrypted under it.
            key_v2 = KeyId(
                purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id=None, version=2, environment="test"
            )
            configure_field_encryption_key(key_v2, os.urandom(32))

            with pytest.raises(DecryptionError):
                column.process_result_value(ciphertext, dialect=None)
        finally:
            clear_field_encryption_key()

    async def test_ciphertext_still_reads_correctly_before_any_rotation(self) -> None:
        """Companion test: proves the prior test's failure is really
        about the key mismatch introduced by rotation, not a general
        break in the encrypt/decrypt round trip."""
        import os

        from responsibleai.db.encryption import (
            EncryptedString,
            clear_field_encryption_key,
            configure_field_encryption_key,
        )
        from responsibleai.governance.crypto.types import KeyId, KeyPurpose

        column = EncryptedString()
        try:
            key_v1 = KeyId(
                purpose=KeyPurpose.FIELD_ENCRYPTION, tenant_id=None, version=1, environment="test"
            )
            configure_field_encryption_key(key_v1, os.urandom(32))
            ciphertext = column.process_bind_param("sensitive-value", dialect=None)
            assert column.process_result_value(ciphertext, dialect=None) == "sensitive-value"
        finally:
            clear_field_encryption_key()
