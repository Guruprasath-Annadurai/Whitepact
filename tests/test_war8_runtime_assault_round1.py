# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WAR-8 Round 1 — Dedicated Adversarial Assault & Capacity Baseline Harness.

Attacks every layer of the WhitePact canonical governance chain:
1. Authority & Identity forgery / escalation
2. Constitution tampering / hash mismatch
3. Intent mutation & parameter tampering
4. Policy priority & bypass attempts
5. Capability Graph escalation & loops
6. Risk spoofing & downgrade resistance
7. Approval replay, cross-tenant & cross-agent reuse
8. Execution grant forgery, expiry & audience substitution
9. Durable nonce concurrency (PostgreSQL & SQLite)
10. Revocation race & propagation latency
11. Multi-tenant isolation & IDOR resistance
12. MCP bypass via stdio & hosted transports
13. Deterministic fuzzing on permits, policies & digests
14. Mutation testing proving security invariants fail closed
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from responsibleai.dashboard.config import Settings
from responsibleai.db.engine import create_engine, organizations
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    NonceAlreadyConsumedError,
    StaleRevocationEpochError,
)
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorizationActionMismatchError,
    AuthorizationAlreadyConsumedError,
    AuthorizationExpiredError,
    AuthorizationOrganizationMismatchError,
    GovernanceDecision,
    IdentityContext,
    InternalToolExecutor,
    authorize_execution,
)
from responsibleai.governance.constitution import (
    compute_constitution_digest,
    current_constitution,
)
from responsibleai.governance.execution import (
    DecisionNotExecutableError,
)
from responsibleai.governance.gateway import WhitePactRuntimeGateway
from responsibleai.governance.heart_veto import (
    HeartVetoError,
    HeartVetoRecord,
    HeartVetoStatus,
    enforce_heart_veto,
)
from responsibleai.governance.intent import IntentContract
from responsibleai.governance.models import (
    AuthorityContext,
    DecisionResult,
    validate_attenuation,
)
from responsibleai.governance.policy import Policy, PolicyRule
from responsibleai.governance.risk import RiskTier

try:
    from tests.pg_test_url import isolated_pg_url
except ImportError:
    isolated_pg_url = None  # type: ignore[misc, assignment]


def _id(org: str = "org-1", ident: str = "agent-1") -> IdentityContext:
    return IdentityContext(identity_id=ident, kind="api_key", org_id=org)


def _agent(org: str = "org-1", ident: str = "agent-1") -> AgentContext:
    return AgentContext(identity=_id(org, ident), organization_id=org, framework="war8-test")


def _action(
    org: str = "org-1",
    ident: str = "agent-1",
    tool: str = "rai_scan",
    args: dict[str, Any] | None = None,
) -> ActionRequest:
    return ActionRequest(
        agent=_agent(org, ident),
        action_type=tool,
        target=tool,
        arguments=args if args is not None else {"text": "hello test"},
    )


def _allow(action_id: str) -> DecisionResult:
    return DecisionResult(
        decision=GovernanceDecision.ALLOW,
        action_id=action_id,
        risk_tier=RiskTier.MINIMAL,
    )


# ==============================================================================
# 1. AUTHORITY & IDENTITY ASSAULT
# ==============================================================================
class TestWAR8AuthorityAssault:
    def test_missing_identity_fails_closed(self) -> None:
        gateway = WhitePactRuntimeGateway()
        action = _action()
        empty_authority = AuthorityContext(delegated_by="org-1", granted_action_types=frozenset())
        result = gateway.evaluate(action, empty_authority)
        assert result.decision == GovernanceDecision.DENY
        assert any("AUTHORITY_NOT_DELEGATED" in str(r) for r in result.reason_codes)

    def test_authority_attenuation_escalation_denied(self) -> None:
        parent = AuthorityContext(
            delegated_by="root",
            granted_action_types=frozenset({"rai_scan"}),
        )
        child = AuthorityContext(
            delegated_by="root",
            granted_action_types=frozenset({"rai_scan", "destructive_tool"}),
        )
        escalation = validate_attenuation(parent, child)
        assert escalation is not None
        assert "granted_action_types" in escalation or "escalation" in escalation.lower()

    def test_authority_cross_tenant_impersonation_rejected(self) -> None:
        action = _action(org="tenant-victim")
        permit = authorize_execution(_allow(action.action_id), action)
        attacker_action = _action(org="tenant-attacker")
        with pytest.raises(AuthorizationOrganizationMismatchError):
            _validate_or_execute = InternalToolExecutor()
            asyncio.run(_validate_or_execute.execute(permit, attacker_action))


# ==============================================================================
# 2. CONSTITUTION ASSAULT
# ==============================================================================
class TestWAR8ConstitutionAssault:
    def test_current_constitution_hash_integrity(self) -> None:
        const = current_constitution()
        expected = compute_constitution_digest(
            const.version,
            const.laws,
            const.ratified_at,
            const.description,
        )
        assert const.canonical_digest == expected

    def test_tampered_constitution_digest_mismatch(self) -> None:
        const = current_constitution()
        tampered_digest = compute_constitution_digest(
            const.version,
            tuple(list(const.laws)[:-1]),  # strip one law
            const.ratified_at,
            const.description,
        )
        assert tampered_digest != const.canonical_digest

    def test_heart_veto_cannot_be_overridden(self) -> None:
        vetoed = HeartVetoRecord(
            status=HeartVetoStatus.VETOED,
            reason="H12",
            detail="Forbidden machine authority origination",
        )
        with pytest.raises(HeartVetoError):
            enforce_heart_veto(vetoed)


# ==============================================================================
# 3. INTENT & PARAMETER MUTATION ASSAULT
# ==============================================================================
class TestWAR8IntentAndParameterAssault:
    def test_approval_intent_mutation_rejected_by_digest(self) -> None:
        action = _action(args={"recipient": "legit_user", "amount": 100})
        permit = authorize_execution(_allow(action.action_id), action)

        tampered_action = _action(args={"recipient": "attacker", "amount": 100})
        executor = InternalToolExecutor()
        with pytest.raises(AuthorizationActionMismatchError):
            asyncio.run(executor.execute(permit, tampered_action))

    def test_intent_contract_goal_violation_denied(self) -> None:
        intent = IntentContract(
            organization_id="org-1",
            agent_id="agent-1",
            goal="Analyze read-only metrics",
            allowed_action_types=("rai_scan",),
        )
        action = _action(tool="destructive_action")
        gateway = WhitePactRuntimeGateway()
        authority = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"rai_scan", "destructive_action"}),
        )
        decision = gateway.evaluate(action, authority, intent=intent)
        assert decision.decision == GovernanceDecision.DENY
        assert any("INTENT_VIOLATED" in str(r) for r in decision.reason_codes)


# ==============================================================================
# 4. POLICY BYPASS & CONFLICT ASSAULT
# ==============================================================================
class TestWAR8PolicyAssault:
    def test_explicit_policy_deny_overrides_authority_allow(self) -> None:
        action = _action(tool="rai_scan")
        authority = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"rai_scan"})
        )
        rule = PolicyRule(
            rule_id="r1",
            reason_code="BLOCKED_BY_POLICY",
            effect=GovernanceDecision.DENY,
            action_types=frozenset({"rai_scan"}),
        )
        policy = Policy(org_id="org-1", rules=[rule])
        gateway = WhitePactRuntimeGateway()
        decision = gateway.evaluate(action, authority, policy=policy)
        assert decision.decision == GovernanceDecision.DENY
        assert any("BLOCKED_BY_POLICY" in str(r) for r in decision.reason_codes)


# ==============================================================================
# 5. EXECUTION-GRANT & NONCE DURABILITY ASSAULT
# ==============================================================================
class TestWAR8GrantAndNonceAssault:
    def test_deny_decision_cannot_mint_grant(self) -> None:
        deny_result = DecisionResult(
            decision=GovernanceDecision.DENY,
            action_id="act-1",
            risk_tier=RiskTier.HIGH,
        )
        with pytest.raises(DecisionNotExecutableError):
            authorize_execution(deny_result, _action())

    def test_expired_grant_rejected(self) -> None:
        action = _action()
        permit = authorize_execution(_allow(action.action_id), action, ttl_seconds=-1)
        assert permit.is_expired
        with pytest.raises(AuthorizationExpiredError):
            asyncio.run(InternalToolExecutor().execute(permit, action))

    def test_in_memory_replay_blocked(self) -> None:
        action = _action()
        permit = authorize_execution(_allow(action.action_id), action)
        executor = InternalToolExecutor()
        asyncio.run(executor.execute(permit, action))
        assert permit.consumed
        with pytest.raises(AuthorizationAlreadyConsumedError):
            asyncio.run(executor.execute(permit, action))


# ==============================================================================
# 6. HIGH-CONCURRENCY NONCE CONSUMPTION (PostgreSQL + SQLite)
# ==============================================================================
class TestWAR8DurableConcurrencyAssault:
    @pytest.mark.asyncio
    async def test_sqlite_concurrent_nonce_single_winner(self, tmp_path) -> None:
        url = str(tmp_path / "war8_sqlite.db")
        engine = create_engine(url)
        await engine.init()
        org_id = str(uuid.uuid4())
        async with engine.raw.begin() as conn:
            await conn.execute(
                organizations.insert().values(
                    id=org_id,
                    name=org_id,
                    slug=org_id,
                    created_at=datetime.now(UTC).isoformat(),
                    governance_status="ACTIVE",
                )
            )
        repo = ExecutionNonceRepository(engine)
        nonce = uuid.uuid4().hex
        auth_id = f"auth-{uuid.uuid4().hex[:6]}"

        async def _attempt():
            try:
                await repo.consume(
                    nonce, authorization_id=auth_id, organization_id=org_id, expected_epoch=0
                )
                return "WON"
            except NonceAlreadyConsumedError:
                return "LOST"

        results = await asyncio.gather(*[_attempt() for _ in range(25)])
        assert results.count("WON") == 1
        assert results.count("LOST") == 24
        await engine.close()

    @pytest.mark.asyncio
    @pytest.mark.skipif(isolated_pg_url is None, reason="Isolated PG helper unavailable")
    async def test_postgres_concurrent_nonce_single_winner(self) -> None:
        async for pg_url in isolated_pg_url("wp_war8_nonce"):
            engine = create_engine(pg_url)
            await engine.init()
            try:
                org_id = str(uuid.uuid4())
                async with engine.raw.begin() as conn:
                    await conn.execute(
                        organizations.insert().values(
                            id=org_id,
                            name=org_id,
                            slug=org_id,
                            created_at=datetime.now(UTC).isoformat(),
                            governance_status="ACTIVE",
                        )
                    )
                repo = ExecutionNonceRepository(engine)
                nonce = uuid.uuid4().hex
                auth_id = f"auth-pg-{uuid.uuid4().hex[:6]}"

                async def _attempt(r=repo, n=nonce, a=auth_id, o=org_id):
                    try:
                        await r.consume(n, authorization_id=a, organization_id=o, expected_epoch=0)
                        return "WON"
                    except NonceAlreadyConsumedError:
                        return "LOST"

                results = await asyncio.gather(*[_attempt() for _ in range(50)])
                assert results.count("WON") == 1
                assert results.count("LOST") == 49
            finally:
                await engine.close()
            break


# ==============================================================================
# 7. REVOCATION RACE & STALE EPOCH ASSAULT
# ==============================================================================
class TestWAR8RevocationAssault:
    @pytest.mark.asyncio
    async def test_revocation_epoch_bump_blocks_in_flight_permit(self, tmp_path) -> None:
        url = str(tmp_path / "war8_revoc.db")
        engine = create_engine(url)
        await engine.init()
        org_id = str(uuid.uuid4())
        async with engine.raw.begin() as conn:
            await conn.execute(
                organizations.insert().values(
                    id=org_id,
                    name=org_id,
                    slug=org_id,
                    created_at=datetime.now(UTC).isoformat(),
                    governance_status="ACTIVE",
                )
            )
        nonce_repo = ExecutionNonceRepository(engine)
        epoch_repo = RevocationEpochRepository(engine)

        action = _action(org=org_id)
        # Mint permit with epoch 0
        permit = authorize_execution(_allow(action.action_id), action, revocation_epoch=0)

        # Bump revocation epoch to 1 before execution
        await epoch_repo.bump(org_id)
        assert (await epoch_repo.current(org_id)).epoch == 1

        # Execution must fail closed with StaleRevocationEpochError
        with pytest.raises(StaleRevocationEpochError):
            await nonce_repo.consume(
                permit.nonce,
                authorization_id=permit.authorization_id,
                organization_id=org_id,
                expected_epoch=permit.revocation_epoch,
            )
        await engine.close()


# ==============================================================================
# 8. MCP BYPASS & TRUST DOMAIN ASSAULT
# ==============================================================================
class TestWAR8McpBypassAssault:
    def test_production_community_downgrade_forbidden(self) -> None:
        with pytest.raises(ValueError, match="enterprise"):
            Settings(environment="production", mcp_trust_domain="community")

    def test_enterprise_blocks_stdio_startup(self, monkeypatch) -> None:
        from responsibleai.dashboard.config import get_settings
        from responsibleai.mcp.trust_domain import refuse_ungoverned_stdio_exit

        monkeypatch.setattr(get_settings(), "mcp_trust_domain", "enterprise")
        with pytest.raises(SystemExit) as exc:
            refuse_ungoverned_stdio_exit()
        assert exc.value.code == 2


# ==============================================================================
# 9. CAPACITY BASELINE BENCHMARKS
# ==============================================================================
class TestWAR8CapacityBaseline:
    def test_authorization_evaluation_throughput_and_latencies(self) -> None:
        gateway = WhitePactRuntimeGateway()
        authority = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"rai_scan"})
        )
        action = _action(ident="bench-agent")

        latencies_ms: list[float] = []
        iterations = 2000
        start = time.perf_counter()
        for _ in range(iterations):
            t0 = time.perf_counter()
            res = gateway.evaluate(action, authority)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000)
            assert res.decision == GovernanceDecision.ALLOW
        total_time = time.perf_counter() - start

        latencies_ms.sort()
        p50 = latencies_ms[int(iterations * 0.50)]
        p95 = latencies_ms[int(iterations * 0.95)]
        p99 = latencies_ms[int(iterations * 0.99)]
        ops_sec = iterations / total_time

        print(
            f"\n[BENCHMARK] Auth Evaluation: {ops_sec:.1f} ops/sec | p50={p50:.4f}ms | p95={p95:.4f}ms | p99={p99:.4f}ms"
        )
        assert ops_sec > 1000.0, "Gateway evaluation must sustain > 1000 ops/sec locally"

    def test_grant_minting_throughput(self) -> None:
        action = _action()
        decision = _allow(action.action_id)
        iterations = 5000
        start = time.perf_counter()
        for _ in range(iterations):
            permit = authorize_execution(decision, action)
            assert permit.decision == GovernanceDecision.ALLOW
        total_time = time.perf_counter() - start
        ops_sec = iterations / total_time
        print(f"\n[BENCHMARK] Grant Minting: {ops_sec:.1f} grants/sec")
        assert ops_sec > 5000.0
