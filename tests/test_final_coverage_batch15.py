# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Batch 15 branch-coverage: mid-tier modules (sovereign simulation/xray/trace,
IAM guard/step-up, MCP governance integration, org_repository fallback,
enterprise verification/issuance/service, dashboard lifespan audit paths)."""

# ruff: noqa: E402

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert

os_env = __import__("os").environ
os_env.setdefault("RAI_AUTH_ENABLED", "false")
os_env.setdefault("RAI_LOG_JSON", "false")
os_env.setdefault("RAI_LOG_LEVEL", "WARNING")
os_env.setdefault("RAI_ALLOW_ALL_ORIGINS", "true")
os_env.setdefault("RAI_AUTO_MIGRATE", "false")

import responsibleai.dashboard.app as app_module
from responsibleai.dashboard.app import app, settings
from responsibleai.db import (
    DelegationRepository,
    EvidenceRepository,
    OrgAuthorityCeilingRepository,
    OrgRepository,
    PolicyRepository,
    WorkflowRuleRepository,
    create_engine,
)
from responsibleai.db.consent_proof_repository import ConsentProofRepository
from responsibleai.db.engine import (
    DatabaseEngine,
    iam_four_eyes_requests,
    iam_jit_grants,
    organizations,
)
from responsibleai.db.execution_nonce_repository import ExecutionNonceRepository
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.db.root_authority_repository import RootAuthorityRepository
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import (
    API_KEY_ISSUANCE_NOT_ALLOWED,
    FORBIDDEN,
    IDENTITY_VERIFICATION_REQUIRED,
    ORGANIZATION_VERIFICATION_REQUIRED,
    EnterpriseError,
)
from responsibleai.enterprise.issuance import CredentialIssuancePolicy
from responsibleai.enterprise.roles import Permission
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.enterprise.verification import HmacVerificationProvider, VerificationService
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
    OrgAuthorityCeiling,
    WhitePactRuntimeGateway,
    WorkflowSequenceRule,
)
from responsibleai.governance.authority_resolver import AuthorityResolver
from responsibleai.governance.evidence import build_evidence_record
from responsibleai.governance.outcome import OutcomeStatus
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.risk import RiskTier
from responsibleai.iam.enums import (
    FourEyesStatus,
    JitGrantStatus,
    PrivilegedAction,
    PrivilegeRiskTier,
    StepUpMethod,
)
from responsibleai.iam.errors import (
    PrivilegedAccessDeniedError,
    StepUpRequiredError,
    StepUpVerificationFailedError,
)
from responsibleai.iam.guard import PrivilegedSurfaceGuard
from responsibleai.iam.models import PrivilegedCallerContext, StepUpProof
from responsibleai.iam.step_up import StepUpVerifier
from responsibleai.integrations.client import TrustClient
from responsibleai.mcp.governance_integration import (
    GovernanceServices,
    _record_outcome,
    apply_governance,
)
from responsibleai.rbac.models import OrgContext, Plan, Role
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.graph import GraphQueryBudget
from responsibleai.sovereign.simulation import (
    MissionDisposition,
    MissionStepSpec,
    simulate_blast_radius,
    simulate_mission,
)
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.trace_builder import build_trace_from_evidence
from responsibleai.sovereign.xray_builder import build_repository_xray

TEST_GOVERNANCE_PURPOSE = "batch15-coverage"


async def _permissive_policy(engine: DatabaseEngine, org_id: str) -> None:
    await PolicyRepository(engine).add_rule(
        org_id,
        PolicyRule(
            rule_id="batch15-allow",
            reason_code="TEST",
            effect=GovernanceDecision.ALLOW,
            risk_tiers=frozenset({RiskTier.LOW, RiskTier.MEDIUM, RiskTier.HIGH}),
        ),
    )


@pytest.fixture
async def guard_db(engine):
    now = datetime.now(UTC).isoformat()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="org_alpha",
                name="Alpha Corp",
                slug="alpha-corp",
                monthly_budget_usd=10000.0,
                created_at=now,
                plan="ENTERPRISE",
            )
        )
    yield engine


@pytest.fixture
async def engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


@pytest.fixture
def store(engine):
    return SovereignCanonicalStore.from_engine(engine)


@pytest.fixture
def sovereign_ctx(engine):
    async def _make():
        org = await OrgRepository(engine).create_org("Sov", f"sov-{uuid.uuid4().hex[:8]}")
        return SovereignContext(organization_id=org.id), org.id

    return _make


@pytest.fixture()
async def client():
    orig_database_url = settings.database_url
    orig_db_path = settings.db_path
    orig_auto_migrate = settings.auto_migrate
    settings.database_url = None
    settings.db_path = ":memory:"
    settings.auto_migrate = False
    try:
        async with LifespanManager(app, startup_timeout=15) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as ac:
                yield ac
    finally:
        settings.database_url = orig_database_url
        settings.db_path = orig_db_path
        settings.auto_migrate = orig_auto_migrate


def _org_ctx(org_id: str, key_id: str = "key-batch15") -> OrgContext:
    return OrgContext(
        key_id=key_id,
        role=Role.ANALYST,
        org_id=org_id,
        org_name="Batch15",
        plan=Plan.ENTERPRISE,
    )


async def _governance_services(
    engine: DatabaseEngine,
    org_id: str,
    key_id: str,
    seed_runtime_authority,
) -> GovernanceServices:
    await seed_runtime_authority(
        engine,
        organization_id=org_id,
        principal_id=key_id,
        action_types=("rai_health", "rai_scan"),
        targets=("rai_health", "rai_scan"),
    )
    return GovernanceServices(
        gateway=WhitePactRuntimeGateway(),
        evidence_repo=EvidenceRepository(engine),
        approval_repo=MagicMock(),
        policy_repo=PolicyRepository(engine),
        trust_client=TrustClient(cache_ttl_minutes=0),
        ceiling_repo=OrgAuthorityCeilingRepository(engine),
        workflow_rule_repo=WorkflowRuleRepository(engine),
        delegation_repo=DelegationRepository(engine),
        nonce_repo=ExecutionNonceRepository(engine),
        epoch_repo=RevocationEpochRepository(engine),
        org_repo=OrgRepository(engine),
        authority_resolver=AuthorityResolver(
            RootAuthorityRepository(engine),
            ConsentProofRepository(engine),
            DelegationRepository(engine),
        ),
    )


async def _user(engine: DatabaseEngine, email: str = "human@example.com") -> str:
    web = WebIdentityRepository(engine)
    user_id, token = await web.register("Human", email, "correct-horse-battery-staple-9")
    assert await web.verify_email(token)
    return user_id


async def _verify_human(engine: DatabaseEngine, user_id: str) -> None:
    provider = HmacVerificationProvider("batch15-secret")
    verification = VerificationService(engine, provider)
    body = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "subject_id": user_id,
        "outcome": "VERIFIED",
        "assurance_level": "government_id",
    }
    ts = datetime.now(UTC).isoformat()
    payload = json.dumps(body, separators=(",", ":")).encode()
    signature = hmac.new(b"batch15-secret", payload + ts.encode(), hashlib.sha256).hexdigest()
    await verification.apply_provider_event(
        payload=payload, signature=signature, timestamp=ts, expected_user_id=user_id
    )


def _actor(user_id: str, org_id: str, role: Role = Role.OWNER) -> Actor:
    return Actor(
        actor_type="human",
        actor_id=user_id,
        user_id=user_id,
        org_id=org_id,
        role=role,
        membership_status="ACTIVE",
        scopes=frozenset(),
        environment_id=None,
    )


# ── sovereign/simulation.py ─────────────────────────────────────────────────


class TestSimulationBatch15:
    async def test_blast_radius_actor_not_found(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        result = await simulate_blast_radius(
            store,
            ctx,
            actor_identity_id="missing-actor",
            hypothetical_extra_capabilities=frozenset({"x"}),
        )
        assert "actor_subtree_unreachable" in result.unknowns

    async def test_blast_radius_with_nested_delegation_and_budget(
        self, store, sovereign_ctx
    ) -> None:
        ctx, org_id = await sovereign_ctx()
        repo = DelegationRepository(store.engine)
        await repo.grant(
            org_id,
            "root-agent",
            granted_action_types=frozenset({"a", "b"}),
            purpose=TEST_GOVERNANCE_PURPOSE,
            granted_by="owner",
        )
        await repo.grant(
            org_id,
            "child-agent",
            granted_action_types=frozenset({"a"}),
            purpose=TEST_GOVERNANCE_PURPOSE,
            granted_by="owner",
            from_identity_id="root-agent",
        )
        tight = GraphQueryBudget(max_nodes=2, max_depth=1, max_edges=1)
        result = await simulate_blast_radius(
            store,
            ctx,
            actor_identity_id="root-agent",
            hypothetical_removed_capabilities=frozenset({"a"}),
            target="sim:target",
            budget=tight,
        )
        assert result.organization_id == org_id

    async def test_blast_radius_extra_capabilities_listed(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        await DelegationRepository(store.engine).grant(
            org_id,
            "agent-x",
            granted_action_types=frozenset({"base"}),
            purpose=TEST_GOVERNANCE_PURPOSE,
            granted_by="owner",
        )
        br = await simulate_blast_radius(
            store,
            ctx,
            actor_identity_id="agent-x",
            hypothetical_extra_capabilities=frozenset({"extra.cap"}),
        )
        assert "extra.cap" in br.newly_reachable_capabilities

    async def test_mission_string_steps_normalized(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        await DelegationRepository(store.engine).grant(
            org_id,
            "agent-m",
            granted_action_types=frozenset({"crm.read"}),
            purpose=TEST_GOVERNANCE_PURPOSE,
            granted_by="owner",
        )
        await _permissive_policy(store.engine, org_id)
        mission = await simulate_mission(store, ctx, agent_id="agent-m", steps=["crm.read"])
        assert mission.steps[0].disposition == MissionDisposition.ALLOW

    async def test_mission_requires_prior_step_unreachable(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        await DelegationRepository(store.engine).grant(
            org_id,
            "agent-m2",
            granted_action_types=frozenset({"a", "b"}),
            purpose=TEST_GOVERNANCE_PURPOSE,
            granted_by="owner",
        )
        steps = [
            MissionStepSpec(action_type="missing.cap", requires_prior_step=False),
            MissionStepSpec(action_type="b", requires_prior_step=True),
        ]
        mission = await simulate_mission(store, ctx, agent_id="agent-m2", steps=steps)
        assert mission.steps[1].disposition == MissionDisposition.UNREACHABLE
        assert mission.would_stop_at_step == 0

    async def test_mission_approval_required_from_effective_authority(
        self, store, sovereign_ctx
    ) -> None:
        ctx, org_id = await sovereign_ctx()
        await DelegationRepository(store.engine).grant(
            org_id,
            "agent-ap",
            granted_action_types=frozenset({"pay.send"}),
            require_approval_for=frozenset({"pay.send"}),
            purpose=TEST_GOVERNANCE_PURPOSE,
            granted_by="owner",
        )
        mission = await simulate_mission(store, ctx, agent_id="agent-ap", steps=["pay.send"])
        assert mission.steps[0].disposition == MissionDisposition.APPROVAL_REQUIRED

    async def test_mission_policy_deny(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        await DelegationRepository(store.engine).grant(
            org_id,
            "agent-deny",
            granted_action_types=frozenset({"danger"}),
            purpose=TEST_GOVERNANCE_PURPOSE,
            granted_by="owner",
        )
        await PolicyRepository(store.engine).add_rule(
            org_id,
            PolicyRule(
                rule_id="deny-danger",
                reason_code="TEST",
                effect=GovernanceDecision.DENY,
                risk_tiers=frozenset({RiskTier.LOW}),
                action_types=frozenset({"danger"}),
            ),
        )
        mission = await simulate_mission(store, ctx, agent_id="agent-deny", steps=["danger"])
        assert mission.steps[0].disposition == MissionDisposition.DENY

    async def test_mission_policy_unknown_when_no_match(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        await DelegationRepository(store.engine).grant(
            org_id,
            "agent-unk",
            granted_action_types=frozenset({"orphan.action"}),
            purpose=TEST_GOVERNANCE_PURPOSE,
            granted_by="owner",
        )
        mission = await simulate_mission(store, ctx, agent_id="agent-unk", steps=["orphan.action"])
        assert mission.steps[0].disposition == MissionDisposition.UNKNOWN

    async def test_mission_policy_require_approval_rule(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        await DelegationRepository(store.engine).grant(
            org_id,
            "agent-pol-ap",
            granted_action_types=frozenset({"audit.run"}),
            purpose=TEST_GOVERNANCE_PURPOSE,
            granted_by="owner",
        )
        await PolicyRepository(store.engine).add_rule(
            org_id,
            PolicyRule(
                rule_id="req-ap",
                reason_code="TEST",
                effect=GovernanceDecision.REQUIRE_APPROVAL,
                risk_tiers=frozenset({RiskTier.LOW}),
                action_types=frozenset({"audit.run"}),
            ),
        )
        mission = await simulate_mission(store, ctx, agent_id="agent-pol-ap", steps=["audit.run"])
        assert mission.steps[0].disposition == MissionDisposition.APPROVAL_REQUIRED

    async def test_mission_invalid_risk_tier_defaults_low(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        await DelegationRepository(store.engine).grant(
            org_id,
            "agent-risk",
            granted_action_types=frozenset({"safe.read"}),
            purpose=TEST_GOVERNANCE_PURPOSE,
            granted_by="owner",
        )
        await _permissive_policy(store.engine, org_id)
        spec = MissionStepSpec(action_type="safe.read", risk_tier="NOT_A_REAL_TIER")
        mission = await simulate_mission(store, ctx, agent_id="agent-risk", steps=[spec])
        assert mission.steps[0].disposition == MissionDisposition.ALLOW


# ── sovereign/xray_builder.py & trace_builder.py ─────────────────────────────


class TestXrayAndTraceBatch15:
    async def test_xray_includes_ceiling_and_policy(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        await OrgAuthorityCeilingRepository(store.engine).set(
            OrgAuthorityCeiling(
                org_id=org_id,
                max_delegation_depth=3,
                allowed_action_types=["crm.read"],
                require_approval_for=["crm.write"],
            )
        )
        await DelegationRepository(store.engine).grant(
            org_id,
            "xray-agent",
            granted_action_types=frozenset({"crm.read", "crm.write"}),
            require_approval_for=frozenset({"crm.write"}),
            purpose=TEST_GOVERNANCE_PURPOSE,
            granted_by="owner",
        )
        graph = await build_repository_xray(store, ctx, budget=GraphQueryBudget(max_nodes=50))
        node_ids = {n.node_id for n in graph.nodes}
        assert f"org:{org_id}" in node_ids
        assert any(n.startswith("ceiling:") for n in node_ids)
        assert any("crm.read" in n for n in node_ids)

    async def test_xray_truncates_on_tight_node_budget(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        graph = await build_repository_xray(store, ctx, budget=GraphQueryBudget(max_nodes=0))
        assert graph.truncated is True

    async def test_xray_evidence_linked_to_actor(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        await DelegationRepository(store.engine).grant(
            org_id,
            "ev-agent",
            granted_action_types=frozenset({"rai_health"}),
            purpose=TEST_GOVERNANCE_PURPOSE,
            granted_by="owner",
        )
        agent = AgentContext(
            identity=IdentityContext(identity_id="ev-agent", kind="agent", org_id=org_id),
            organization_id=org_id,
            agent_id="ev-agent",
        )
        action = ActionRequest(agent=agent, action_type="rai_health", target="rai_health")
        gw = WhitePactRuntimeGateway()
        authority = AuthorityContext(
            delegated_by="owner", granted_action_types=frozenset({"rai_health"})
        )
        decision = gw.evaluate(action, authority)
        evidence = build_evidence_record(action, agent, authority, decision)
        await store.evidence.record(evidence)
        graph = await build_repository_xray(store, ctx, evidence_limit=5)
        assert any(n.node_id.startswith("evidence:") for n in graph.nodes)

    async def test_trace_missing_principal_on_evidence(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        agent = AgentContext(
            identity=IdentityContext(identity_id="ghost", kind="agent", org_id=org_id),
            organization_id=org_id,
            agent_id="ghost",
        )
        action = ActionRequest(agent=agent, action_type="x", target="x")
        authority = AuthorityContext(delegated_by="owner", granted_action_types=frozenset({"x"}))
        decision = DecisionResult(
            decision=GovernanceDecision.DENY,
            action_id=action.action_id,
            reason_codes=["TEST"],
        )
        evidence = build_evidence_record(action, agent, authority, decision)
        evidence = replace(evidence, identity_id="", agent_id="")
        await store.evidence.record(evidence)
        trace = await build_trace_from_evidence(store, ctx, evidence.evidence_id)
        assert any(s.stage.value == "principal" and s.status == "MISSING" for s in trace.stages)

    async def test_trace_delegation_chain_present(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        await DelegationRepository(store.engine).grant(
            org_id,
            "trace-agent",
            granted_action_types=frozenset({"t.act"}),
            purpose=TEST_GOVERNANCE_PURPOSE,
            granted_by="owner",
        )
        agent = AgentContext(
            identity=IdentityContext(identity_id="trace-agent", kind="agent", org_id=org_id),
            organization_id=org_id,
            agent_id="trace-agent",
        )
        action = ActionRequest(agent=agent, action_type="t.act", target="t.act")
        authority = AuthorityContext(
            delegated_by="owner", granted_action_types=frozenset({"t.act"})
        )
        decision = WhitePactRuntimeGateway().evaluate(action, authority)
        evidence = build_evidence_record(action, agent, authority, decision)
        await store.evidence.record(evidence)
        trace = await build_trace_from_evidence(store, ctx, evidence.evidence_id)
        assert any(s.stage.value == "delegation" and s.status == "PRESENT" for s in trace.stages)

    async def test_trace_unknown_decision_value(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        agent = AgentContext(
            identity=IdentityContext(identity_id="bad-dec", kind="agent", org_id=org_id),
            organization_id=org_id,
            agent_id="bad-dec",
        )
        action = ActionRequest(agent=agent, action_type="x", target="x")
        authority = AuthorityContext(delegated_by="owner", granted_action_types=frozenset({"x"}))
        decision = WhitePactRuntimeGateway().evaluate(action, authority)
        evidence = build_evidence_record(action, agent, authority, decision)
        evidence = replace(evidence, decision="NOT_A_REAL_DECISION")
        await store.evidence.record(evidence)
        trace = await build_trace_from_evidence(store, ctx, evidence.evidence_id)
        assert any(s.stage.value == "judgment" and s.status == "UNKNOWN" for s in trace.stages)

    async def test_trace_approval_reference_missing_row(self, store, sovereign_ctx) -> None:
        ctx, org_id = await sovereign_ctx()
        agent = AgentContext(
            identity=IdentityContext(identity_id="ap-miss", kind="agent", org_id=org_id),
            organization_id=org_id,
            agent_id="ap-miss",
        )
        action = ActionRequest(agent=agent, action_type="x", target="x")
        authority = AuthorityContext(delegated_by="owner", granted_action_types=frozenset({"x"}))
        decision = WhitePactRuntimeGateway().evaluate(action, authority)
        evidence = build_evidence_record(action, agent, authority, decision)
        evidence = replace(evidence, approval_id="missing-approval-id")
        await store.evidence.record(evidence)
        trace = await build_trace_from_evidence(store, ctx, evidence.evidence_id)
        assert any(s.stage.value == "approval" and s.status == "UNKNOWN" for s in trace.stages)


# ── iam/step_up.py ───────────────────────────────────────────────────────────


class TestStepUpBatch15:
    async def test_missing_proof_issues_nonce_and_raises(self, engine) -> None:
        verifier = StepUpVerifier(engine)
        with pytest.raises(StepUpRequiredError) as exc:
            await verifier.verify_and_consume_step_up(
                org_id="org-1",
                principal_id="p-1",
                action="ROTATE_API_KEY",
                risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
                proof=None,
            )
        assert exc.value.required_nonce.startswith("wp_nonce_")

    async def test_invalid_auth_time_rejected(self, engine) -> None:
        verifier = StepUpVerifier(engine)
        nonce = await verifier.issue_step_up_nonce(org_id="org-1", principal_id="p-1", action="A")
        proof = StepUpProof(
            nonce=nonce,
            method=StepUpMethod.MFA_TOTP,
            auth_time="not-a-timestamp",
            token_or_code="123456",
        )
        with pytest.raises(StepUpVerificationFailedError, match="Invalid auth_time"):
            await verifier.verify_and_consume_step_up(
                org_id="org-1",
                principal_id="p-1",
                action="A",
                risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
                proof=proof,
            )

    async def test_stale_auth_time_for_critical_window(self, engine) -> None:
        verifier = StepUpVerifier(engine)
        nonce = await verifier.issue_step_up_nonce(org_id="org-1", principal_id="p-1", action="A")
        old = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
        proof = StepUpProof(
            nonce=nonce,
            method=StepUpMethod.MFA_TOTP,
            auth_time=old,
            token_or_code="123456",
        )
        with pytest.raises(StepUpVerificationFailedError, match="freshness window"):
            await verifier.verify_and_consume_step_up(
                org_id="org-1",
                principal_id="p-1",
                action="A",
                risk_tier=PrivilegeRiskTier.PRIVILEGED_CRITICAL,
                proof=proof,
            )

    async def test_target_resource_mismatch(self, engine) -> None:
        verifier = StepUpVerifier(engine)
        nonce = await verifier.issue_step_up_nonce(
            org_id="org-1",
            principal_id="p-1",
            action="A",
            target_resource_id="resource-expected",
        )
        proof = StepUpProof(
            nonce=nonce,
            method=StepUpMethod.MFA_TOTP,
            auth_time=datetime.now(UTC).isoformat(),
            token_or_code="123456",
        )
        with pytest.raises(StepUpVerificationFailedError, match="target resource mismatch"):
            await verifier.verify_and_consume_step_up(
                org_id="org-1",
                principal_id="p-1",
                action="A",
                risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
                proof=proof,
                target_resource_id="other-resource",
            )

    async def test_webauthn_unsupported_stub(self, engine) -> None:
        verifier = StepUpVerifier(engine)
        nonce = await verifier.issue_step_up_nonce(org_id="org-1", principal_id="p-1", action="A")
        proof = StepUpProof(
            nonce=nonce,
            method=StepUpMethod.WEBAUTHN,
            auth_time=datetime.now(UTC).isoformat(),
            token_or_code="unsupported_stub",
        )
        with pytest.raises(StepUpVerificationFailedError, match="Unsupported WebAuthn"):
            await verifier.verify_and_consume_step_up(
                org_id="org-1",
                principal_id="p-1",
                action="A",
                risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
                proof=proof,
            )

    async def test_oidc_short_token_rejected(self, engine) -> None:
        verifier = StepUpVerifier(engine)
        nonce = await verifier.issue_step_up_nonce(org_id="org-1", principal_id="p-1", action="A")
        proof = StepUpProof(
            nonce=nonce,
            method=StepUpMethod.OIDC_AUTH_TIME,
            auth_time=datetime.now(UTC).isoformat(),
            token_or_code="short",
        )
        with pytest.raises(StepUpVerificationFailedError, match="Invalid OIDC"):
            await verifier.verify_and_consume_step_up(
                org_id="org-1",
                principal_id="p-1",
                action="A",
                risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
                proof=proof,
            )


# ── iam/guard.py ─────────────────────────────────────────────────────────────


class TestGuardBatch15:
    async def test_jit_grant_invalid_id_denied(self, guard_db, seed_trust_employment) -> None:
        await seed_trust_employment(guard_db, org_id="org_alpha", principal_id="admin_alpha")
        guard = PrivilegedSurfaceGuard(guard_db)
        caller = PrivilegedCallerContext(
            principal_id="admin_alpha", org_id="org_alpha", role=Role.ADMIN
        )
        with pytest.raises(PrivilegedAccessDeniedError, match="Invalid JIT"):
            await guard.authorize_privileged_operation(
                caller=caller,
                target_org_id="org_alpha",
                action=PrivilegedAction.MODIFY_POLICY_RULE,
                jit_grant_id="jit_missing",
            )

    async def test_jit_grant_wrong_action_denied(self, guard_db, seed_trust_employment) -> None:
        await seed_trust_employment(guard_db, org_id="org_alpha", principal_id="admin_alpha")
        now = datetime.now(UTC)
        grant_id = f"jit_{uuid.uuid4().hex}"
        async with guard_db.raw.begin() as conn:
            await conn.execute(
                insert(iam_jit_grants).values(
                    id=grant_id,
                    org_id="org_alpha",
                    principal_id="admin_alpha",
                    target_role="ADMIN",
                    allowed_actions_json=json.dumps([PrivilegedAction.CREATE_API_KEY.value]),
                    status=JitGrantStatus.ACTIVE.value,
                    expires_at=(now + timedelta(hours=1)).isoformat(),
                    requested_at=now.isoformat(),
                    justification="test",
                )
            )
        guard = PrivilegedSurfaceGuard(guard_db)
        caller = PrivilegedCallerContext(
            principal_id="admin_alpha", org_id="org_alpha", role=Role.ADMIN
        )
        proof = StepUpProof(
            nonce=await StepUpVerifier(guard_db).issue_step_up_nonce(
                org_id="org_alpha",
                principal_id="admin_alpha",
                action=PrivilegedAction.MODIFY_POLICY_RULE.value,
            ),
            method=StepUpMethod.MFA_TOTP,
            auth_time=datetime.now(UTC).isoformat(),
            token_or_code="123456",
        )
        with pytest.raises(PrivilegedAccessDeniedError, match="not authorized by JIT"):
            await guard.authorize_privileged_operation(
                caller=caller,
                target_org_id="org_alpha",
                action=PrivilegedAction.MODIFY_POLICY_RULE,
                jit_grant_id=grant_id,
                step_up_proof=proof,
            )

    async def test_four_eyes_action_mismatch_denied(self, guard_db, seed_trust_employment) -> None:
        await seed_trust_employment(guard_db, org_id="org_alpha", principal_id="admin_alpha")
        fe_id = f"fe_{uuid.uuid4().hex}"
        now = datetime.now(UTC)
        async with guard_db.raw.begin() as conn:
            await conn.execute(
                insert(iam_four_eyes_requests).values(
                    id=fe_id,
                    org_id="org_alpha",
                    requester_principal_id="admin_alpha",
                    approver_principal_id="admin_checker",
                    action=PrivilegedAction.CREATE_API_KEY.value,
                    parameters_json="{}",
                    request_digest="digest",
                    status=FourEyesStatus.APPROVED.value,
                    expires_at=(now + timedelta(hours=1)).isoformat(),
                    created_at=now.isoformat(),
                )
            )
        guard = PrivilegedSurfaceGuard(guard_db)
        caller = PrivilegedCallerContext(
            principal_id="admin_alpha", org_id="org_alpha", role=Role.ADMIN
        )
        proof = StepUpProof(
            nonce=await StepUpVerifier(guard_db).issue_step_up_nonce(
                org_id="org_alpha",
                principal_id="admin_alpha",
                action=PrivilegedAction.MUTATE_CRITICAL_POLICY.value,
            ),
            method=StepUpMethod.MFA_TOTP,
            auth_time=datetime.now(UTC).isoformat(),
            token_or_code="123456",
        )
        with pytest.raises(PrivilegedAccessDeniedError, match="action mismatch"):
            await guard.authorize_privileged_operation(
                caller=caller,
                target_org_id="org_alpha",
                action=PrivilegedAction.MUTATE_CRITICAL_POLICY,
                four_eyes_approval_id=fe_id,
                step_up_proof=proof,
            )

    async def test_transfer_root_requires_sovereign_root(
        self, guard_db, seed_trust_employment
    ) -> None:
        await seed_trust_employment(guard_db, org_id="org_alpha", principal_id="admin_alpha")
        fe_id = f"fe_{uuid.uuid4().hex}"
        now = datetime.now(UTC)
        async with guard_db.raw.begin() as conn:
            await conn.execute(
                insert(iam_four_eyes_requests).values(
                    id=fe_id,
                    org_id="org_alpha",
                    requester_principal_id="admin_alpha",
                    approver_principal_id="admin_checker",
                    action=PrivilegedAction.DESTROY_TENANT.value,
                    parameters_json="{}",
                    request_digest="digest",
                    status=FourEyesStatus.APPROVED.value,
                    expires_at=(now + timedelta(hours=1)).isoformat(),
                    created_at=now.isoformat(),
                )
            )
        guard = PrivilegedSurfaceGuard(guard_db)
        caller = PrivilegedCallerContext(
            principal_id="admin_alpha", org_id="org_alpha", role=Role.ADMIN
        )
        proof = StepUpProof(
            nonce=await StepUpVerifier(guard_db).issue_step_up_nonce(
                org_id="org_alpha",
                principal_id="admin_alpha",
                action=PrivilegedAction.DESTROY_TENANT.value,
            ),
            method=StepUpMethod.MFA_TOTP,
            auth_time=datetime.now(UTC).isoformat(),
            token_or_code="123456",
        )
        with pytest.raises(PrivilegedAccessDeniedError, match="Sovereign Root"):
            await guard.authorize_privileged_operation(
                caller=caller,
                target_org_id="org_alpha",
                action=PrivilegedAction.DESTROY_TENANT,
                step_up_proof=proof,
                four_eyes_approval_id=fe_id,
            )


# ── mcp/governance_integration.py ───────────────────────────────────────────


class TestGovernanceIntegrationBatch15:
    async def test_revoked_delegation_denied_before_gateway(
        self, engine, seed_runtime_authority
    ) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("Gov2", f"g2-{uuid.uuid4().hex[:8]}")
        key_rec, _ = await repo.create_key(org.id, "k", role=Role.ANALYST)
        services = await _governance_services(engine, org.id, key_rec.id, seed_runtime_authority)
        await services.delegation_repo.revoke_branch(
            org.id, key_rec.id, revoked_by=f"owner:{org.id}", reason="test"
        )
        outcome = await apply_governance(
            "rai_health",
            {},
            _org_ctx(org.id, key_rec.id),
            services,
            purpose=TEST_GOVERNANCE_PURPOSE,
        )
        assert outcome.proceed is False
        assert outcome.blocked_response is not None
        assert outcome.blocked_response["error"] == "governance_denied"

    async def test_expired_delegation_denied(self, engine, seed_runtime_authority) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("Exp", f"exp-{uuid.uuid4().hex[:8]}")
        key_rec, _ = await repo.create_key(org.id, "k", role=Role.ANALYST)
        services = await _governance_services(engine, org.id, key_rec.id, seed_runtime_authority)
        past = datetime.now(UTC) - timedelta(minutes=5)
        await DelegationRepository(engine).grant(
            org.id,
            key_rec.id,
            granted_action_types=frozenset({"rai_health"}),
            purpose=TEST_GOVERNANCE_PURPOSE,
            granted_by=f"owner:{org.id}",
            expires_at=past,
        )
        outcome = await apply_governance(
            "rai_health",
            {},
            _org_ctx(org.id, key_rec.id),
            services,
            purpose=TEST_GOVERNANCE_PURPOSE,
        )
        assert outcome.proceed is False
        codes = outcome.blocked_response.get("reason_codes", [])
        assert any("AUTHORITY" in c for c in codes)

    async def test_ceiling_escalation_denied(self, engine, seed_runtime_authority) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("Ceil", f"ceil-{uuid.uuid4().hex[:8]}")
        key_rec, _ = await repo.create_key(org.id, "k", role=Role.ANALYST)
        services = await _governance_services(engine, org.id, key_rec.id, seed_runtime_authority)
        await OrgAuthorityCeilingRepository(engine).set(
            OrgAuthorityCeiling(org_id=org.id, allowed_action_types=["rai_scan"])
        )
        outcome = await apply_governance(
            "rai_health",
            {},
            _org_ctx(org.id, key_rec.id),
            services,
            purpose=TEST_GOVERNANCE_PURPOSE,
        )
        assert outcome.proceed is False

    async def test_workflow_sequence_denied_on_third_step(
        self, engine, seed_runtime_authority
    ) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("Wf", f"wf-{uuid.uuid4().hex[:8]}")
        key_rec, _ = await repo.create_key(org.id, "k", role=Role.ANALYST)
        services = await _governance_services(engine, org.id, key_rec.id, seed_runtime_authority)
        await WorkflowRuleRepository(engine).add_rule(
            org.id,
            WorkflowSequenceRule(
                rule_id="seq-1",
                action_types=("rai_health", "rai_scan", "rai_health"),
                window_minutes=60,
            ),
        )
        agent = AgentContext(
            identity=IdentityContext(identity_id=key_rec.id, kind="api_key", org_id=org.id),
            organization_id=org.id,
            agent_id=key_rec.id,
        )
        for tool in ("rai_health", "rai_scan"):
            action = ActionRequest(agent=agent, action_type=tool, target=tool)
            authority = AuthorityContext(
                delegated_by=f"owner:{org.id}", granted_action_types=frozenset({tool})
            )
            decision = services.gateway.evaluate(action, authority)
            await services.evidence_repo.record(
                build_evidence_record(action, agent, authority, decision)
            )
        outcome = await apply_governance(
            "rai_health",
            {},
            _org_ctx(org.id, key_rec.id),
            services,
            purpose=TEST_GOVERNANCE_PURPOSE,
        )
        assert outcome.proceed is False

    async def test_record_outcome_unknown_fallback(self) -> None:
        outcome_repo = AsyncMock()
        outcome_repo.record.side_effect = [RuntimeError("fail"), RuntimeError("fail again")]
        services = GovernanceServices(
            gateway=WhitePactRuntimeGateway(),
            evidence_repo=AsyncMock(),
            approval_repo=AsyncMock(),
            policy_repo=AsyncMock(),
            trust_client=AsyncMock(),
            outcome_repo=outcome_repo,
        )
        ok = await _record_outcome(
            services, "ev-1", "act-1", OutcomeStatus.SUCCEEDED, organization_id="org-1"
        )
        assert ok is False
        assert outcome_repo.record.await_count == 2


# ── db/org_repository.py ─────────────────────────────────────────────────────


class TestOrgRepositoryBatch15:
    async def test_execute_org_select_fallback(self, engine) -> None:
        from sqlalchemy import select

        from responsibleai.db.engine import organizations as orgs_table
        from responsibleai.db.org_repository import _BASE_ORG_COLUMNS

        repo = OrgRepository(engine)
        org = await repo.create_org("Fallback", f"fb-{uuid.uuid4().hex[:8]}")

        async def _fallback_execute(conn, where_clause=None):
            await conn.rollback()
            fallback_stmt = select(*_BASE_ORG_COLUMNS).select_from(orgs_table)
            if where_clause is not None:
                fallback_stmt = fallback_stmt.where(where_clause)
            return await conn.execute(fallback_stmt)

        repo._execute_org_select = _fallback_execute  # type: ignore[method-assign]
        fetched = await repo.get_org(org.id)
        assert fetched is not None
        assert fetched.id == org.id

    async def test_paddle_subscription_id_must_use_sub_prefix(self, engine) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("Pdl", f"pdl-{uuid.uuid4().hex[:8]}")
        with pytest.raises(ValueError, match="sub_"):
            await repo.apply_paddle_entitlement(
                org_id=org.id,
                customer_id="ctm_x",
                subscription_id="bad_sub",
                plan=Plan.PRO,
                occurred_at=datetime.now(UTC).isoformat(),
            )

    async def test_paddle_stale_occurred_at_returns_false(self, engine) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("Stale", f"st-{uuid.uuid4().hex[:8]}")
        ts_new = datetime.now(UTC).isoformat()
        assert await repo.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_stale",
            subscription_id=None,
            plan=Plan.PRO,
            occurred_at=ts_new,
        )
        ts_old = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        assert (
            await repo.apply_paddle_entitlement(
                org_id=org.id,
                customer_id="ctm_stale",
                subscription_id=None,
                plan=Plan.FREE,
                occurred_at=ts_old,
            )
            is False
        )


# ── enterprise/verification.py & issuance.py ────────────────────────────────


class TestVerificationBatch15:
    def test_hmac_provider_rejects_bad_signature(self) -> None:
        provider = HmacVerificationProvider("secret")
        with pytest.raises(EnterpriseError):
            provider.verify_webhook(
                payload=b"{}", signature="bad", timestamp="2020-01-01T00:00:00+00:00"
            )

    def test_hmac_provider_rejects_malformed_event(self) -> None:
        provider = HmacVerificationProvider("secret")
        ts = datetime.now(UTC).isoformat()
        payload = b'{"no_event_id":true}'
        sig = hmac.new(b"secret", payload + ts.encode(), hashlib.sha256).hexdigest()
        with pytest.raises(EnterpriseError):
            provider.verify_webhook(payload=payload, signature=sig, timestamp=ts)

    def test_hmac_provider_rejects_verified_without_subject(self) -> None:
        provider = HmacVerificationProvider("secret")
        ts = datetime.now(UTC).isoformat()
        payload = b'{"event_id":"e1","verified":true}'
        sig = hmac.new(b"secret", payload + ts.encode(), hashlib.sha256).hexdigest()
        with pytest.raises(EnterpriseError):
            provider.verify_webhook(payload=payload, signature=sig, timestamp=ts)

    async def test_get_human_status_user_missing(self, engine) -> None:
        svc = VerificationService(engine, HmacVerificationProvider("s"))
        with pytest.raises(EnterpriseError) as exc:
            await svc.get_human_status(str(uuid.uuid4()))
        assert exc.value.code == FORBIDDEN

    async def test_apply_provider_unrecognized_human_outcome(self, engine) -> None:
        provider = HmacVerificationProvider("sec")
        svc = VerificationService(engine, provider)
        user_id = await _user(engine)
        body = {"event_id": "e-bad", "subject_id": user_id, "outcome": "MYSTERY"}
        ts = datetime.now(UTC).isoformat()
        payload = json.dumps(body).encode()
        sig = hmac.new(b"sec", payload + ts.encode(), hashlib.sha256).hexdigest()
        with pytest.raises(EnterpriseError):
            await svc.apply_provider_event(
                payload=payload, signature=sig, timestamp=ts, expected_user_id=user_id
            )


class TestIssuanceBatch15:
    async def test_issuance_denied_without_identity_verified(self, engine) -> None:
        user_id = await _user(engine)
        iam = EnterpriseIAM(engine)
        org = await iam.create_workspace(
            actor_user_id=user_id,
            name="Iss",
            slug=f"iss-{uuid.uuid4().hex[:8]}",
            kind="ORGANIZATION",
        )
        envs = await iam.list_environments(_actor(user_id, org["id"]), org["id"])
        env_id = next(e["id"] for e in envs if e["type"] == "DEVELOPMENT")
        policy = CredentialIssuancePolicy(
            engine, VerificationService(engine, HmacVerificationProvider("s"))
        )
        decision = await policy.evaluate(
            principal_user_id=user_id,
            organization_id=org["id"],
            environment_id=env_id,
            requested_scopes=("usage:read",),
        )
        assert decision.allowed is False
        assert decision.reason_code == IDENTITY_VERIFICATION_REQUIRED

    async def test_issuance_unknown_scope_denied(self, engine) -> None:
        user_id = await _user(engine)
        await _verify_human(engine, user_id)
        iam = EnterpriseIAM(engine)
        org = await iam.create_workspace(
            actor_user_id=user_id,
            name="Iss2",
            slug=f"iss2-{uuid.uuid4().hex[:8]}",
            kind="ORGANIZATION",
        )
        envs = await iam.list_environments(_actor(user_id, org["id"]), org["id"])
        env_id = next(e["id"] for e in envs if e["type"] == "DEVELOPMENT")
        policy = CredentialIssuancePolicy(
            engine, VerificationService(engine, HmacVerificationProvider("s"))
        )
        decision = await policy.evaluate(
            principal_user_id=user_id,
            organization_id=org["id"],
            environment_id=env_id,
            requested_scopes=("not:a-real-scope",),
        )
        assert decision.allowed is False
        assert decision.reason_code == API_KEY_ISSUANCE_NOT_ALLOWED

    async def test_issuance_production_requires_org_verified(self, engine) -> None:
        user_id = await _user(engine)
        await _verify_human(engine, user_id)
        iam = EnterpriseIAM(engine)
        org = await iam.create_workspace(
            actor_user_id=user_id,
            name="Iss3",
            slug=f"iss3-{uuid.uuid4().hex[:8]}",
            kind="ORGANIZATION",
        )
        actor = _actor(user_id, org["id"])
        envs = await iam.list_environments(actor, org["id"])
        prod_id = next(e["id"] for e in envs if e["type"] == "PRODUCTION")
        policy = CredentialIssuancePolicy(
            engine, VerificationService(engine, HmacVerificationProvider("s"))
        )
        decision = await policy.evaluate(
            principal_user_id=user_id,
            organization_id=org["id"],
            environment_id=prod_id,
            requested_scopes=("usage:read",),
        )
        assert decision.allowed is False
        assert decision.reason_code == ORGANIZATION_VERIFICATION_REQUIRED


# ── enterprise/service.py ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_iam_authorize_production_gate_b_monkeypatch(engine, monkeypatch) -> None:
    monkeypatch.setattr("responsibleai.enterprise.service.PRODUCTION_GATE_B_OPEN", True)
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org = await iam.create_workspace(
        actor_user_id=owner,
        name="Gate",
        slug=f"gate-{uuid.uuid4().hex[:8]}",
        kind="ORGANIZATION",
    )
    with pytest.raises(EnterpriseError) as exc:
        await iam.authorize(_actor(owner, org["id"]), Permission.ORG_VIEW, org_id=org["id"])
    assert exc.value.code == FORBIDDEN


# ── dashboard/app.py lifespan + audit middleware ─────────────────────────────


class TestDashboardBatch15:
    @pytest.mark.asyncio
    async def test_lifespan_multi_replica_warning_branch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "database_url", None)
        monkeypatch.setattr(settings, "db_path", ":memory:")
        monkeypatch.setattr(settings, "auto_migrate", False)
        monkeypatch.setattr(settings, "multi_replica", True)
        monkeypatch.setattr(settings, "redis_url", None)
        monkeypatch.setattr(settings, "saml_idp_entity_id", None)
        monkeypatch.setattr(settings, "oidc_issuer", None)
        async with LifespanManager(app, startup_timeout=15):
            pass

    @pytest.mark.asyncio
    async def test_audit_middleware_non_skip_path_writes(
        self, client: AsyncClient, monkeypatch
    ) -> None:
        audit = AsyncMock()
        audit.write = AsyncMock()
        monkeypatch.setattr(app_module, "_audit_repo", audit)
        response = await client.get("/api/health")
        assert response.status_code == 200
        for _ in range(20):
            if audit.write.await_count:
                break
            await asyncio.sleep(0.05)
        assert audit.write.await_count >= 1
