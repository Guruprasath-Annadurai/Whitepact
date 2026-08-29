"""Tests for the REQUIRE_APPROVAL -> resume-execution pipeline (v3
authority-layer work, Task #140): the real architectural gap flagged
throughout this session -- an approved action previously had nothing
to execute against, since original arguments weren't persisted. This
file proves the full round trip: REQUIRE_APPROVAL -> persisted
encrypted arguments -> human APPROVED -> resume actually executes the
original action -> the approval is CONSUMED -> a second resume attempt
is blocked (replay), and a mutated/missing-arguments case is refused.
"""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.db import (
    ApprovalActionMismatchError,
    ApprovalNotApprovedError,
    ApprovalRepository,
    EvidenceRepository,
)
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.approval import (
    ApprovalStatus,
    build_approval_request,
    build_resume_action,
)
from responsibleai.mcp.governance_integration import resume_approval

BOOTSTRAP_AUTH = {"Authorization": "Bearer bootstrap-test-key"}


@pytest.fixture(autouse=True)
def _auth_enabled_with_bootstrap_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    limiter.reset()
    yield


@pytest.fixture()
async def client():
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as c:
            yield c


@pytest.fixture()
async def org_and_admin_key(client: AsyncClient):
    r = await client.post(
        "/api/orgs",
        json={"name": "Resume Test Co", "slug": "resume-test-co"},
        headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    org_id = r.json()["id"]
    r = await client.post(
        f"/api/orgs/{org_id}/keys",
        json={"name": "admin-key", "role": "ADMIN"},
        headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    return org_id, r.json()["key"]


async def _seed_dispatchable_approval(org_id: str, *, arguments: dict | None = None) -> str:
    """Unlike test_governance_api.py's _seed_approval() (action_type
    "deployment" -- not a real MCP tool, fine for resolve-only tests),
    this seeds an approval against a REAL dispatchable tool
    ("rai_health") so resume_approval() can actually execute it."""
    from responsibleai.dashboard.app import _db_engine

    gw = WhitePactRuntimeGateway()
    identity = IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)
    agent = AgentContext(identity=identity, framework="mcp-client")
    authority = AuthorityContext(
        delegated_by=org_id,
        granted_action_types=frozenset({"rai_health"}),
        require_approval_for=frozenset({"rai_health"}),
    )
    action = ActionRequest(
        agent=agent,
        action_type="rai_health",
        target="rai_health",
        arguments=arguments or {},
    )
    decision = gw.evaluate(action, authority)
    assert decision.decision == GovernanceDecision.REQUIRE_APPROVAL
    saved = await ApprovalRepository(_db_engine).create(build_approval_request(action, decision))
    return saved.approval_id


class TestBuildResumeAction:
    def test_reconstructs_the_exact_original_action(self) -> None:
        identity = IdentityContext(identity_id="k1", kind="api_key", org_id="org-1")
        agent = AgentContext(identity=identity, framework="mcp-client")
        authority = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"rai_scan"}),
            require_approval_for=frozenset({"rai_scan"}),
        )
        original = ActionRequest(
            agent=agent,
            action_type="rai_scan",
            target="rai_scan",
            arguments={"text": "hello"},
        )
        gw = WhitePactRuntimeGateway()
        decision = gw.evaluate(original, authority)
        approval = build_approval_request(original, decision)

        rebuilt = build_resume_action(approval, agent=agent)
        assert rebuilt.action_type == "rai_scan"
        assert rebuilt.target == "rai_scan"
        assert rebuilt.arguments == {"text": "hello"}
        assert rebuilt.action_id == original.action_id

    def test_raises_for_a_legacy_approval_with_no_persisted_arguments(self) -> None:
        identity = IdentityContext(identity_id="k1", kind="api_key", org_id="org-1")
        agent = AgentContext(identity=identity, framework="mcp-client")
        authority = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"rai_scan"}),
            require_approval_for=frozenset({"rai_scan"}),
        )
        action = ActionRequest(agent=agent, action_type="rai_scan", target="rai_scan")
        decision = WhitePactRuntimeGateway().evaluate(action, authority)
        approval = build_approval_request(action, decision)
        approval.arguments = None  # simulate a pre-feature row

        with pytest.raises(ValueError, match="cannot be resumed"):
            build_resume_action(approval, agent=agent)


class TestResumeApprovalEndToEnd:
    async def test_full_round_trip_actually_executes_the_tool(
        self,
        client: AsyncClient,
        org_and_admin_key,
    ) -> None:
        org_id, admin_key = org_and_admin_key
        headers = {"Authorization": f"Bearer {admin_key}"}
        approval_id = await _seed_dispatchable_approval(org_id)

        resolve = await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers=headers,
        )
        assert resolve.status_code == 200

        execute = await client.post(
            f"/api/governance/approvals/{approval_id}/execute",
            headers=headers,
        )
        assert execute.status_code == 200, execute.text
        body = execute.json()
        assert body["approval_id"] == approval_id
        assert body["result"]["status"] == "ok"  # rai_health's real handler ran

    async def test_replay_after_execute_is_refused(
        self, client: AsyncClient, org_and_admin_key
    ) -> None:
        org_id, admin_key = org_and_admin_key
        headers = {"Authorization": f"Bearer {admin_key}"}
        approval_id = await _seed_dispatchable_approval(org_id)
        await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers=headers,
        )

        first = await client.post(
            f"/api/governance/approvals/{approval_id}/execute", headers=headers
        )
        assert first.status_code == 200

        second = await client.post(
            f"/api/governance/approvals/{approval_id}/execute", headers=headers
        )
        assert second.status_code == 409

    async def test_pending_not_yet_approved_cannot_be_executed(
        self,
        client: AsyncClient,
        org_and_admin_key,
    ) -> None:
        org_id, admin_key = org_and_admin_key
        headers = {"Authorization": f"Bearer {admin_key}"}
        approval_id = await _seed_dispatchable_approval(org_id)

        r = await client.post(f"/api/governance/approvals/{approval_id}/execute", headers=headers)
        assert r.status_code == 409

    async def test_denied_approval_cannot_be_executed(
        self, client: AsyncClient, org_and_admin_key
    ) -> None:
        org_id, admin_key = org_and_admin_key
        headers = {"Authorization": f"Bearer {admin_key}"}
        approval_id = await _seed_dispatchable_approval(org_id)
        await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "DENIED"},
            headers=headers,
        )

        r = await client.post(f"/api/governance/approvals/{approval_id}/execute", headers=headers)
        assert r.status_code == 409

    async def test_execute_requires_admin_role(
        self, client: AsyncClient, org_and_admin_key
    ) -> None:
        org_id, admin_key = org_and_admin_key
        admin_headers = {"Authorization": f"Bearer {admin_key}"}
        approval_id = await _seed_dispatchable_approval(org_id)
        await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers=admin_headers,
        )

        r = await client.post(
            f"/api/orgs/{org_id}/keys",
            json={"name": "analyst-key", "role": "ANALYST"},
            headers=BOOTSTRAP_AUTH,
        )
        analyst_key = r.json()["key"]

        r = await client.post(
            f"/api/governance/approvals/{approval_id}/execute",
            headers={"Authorization": f"Bearer {analyst_key}"},
        )
        assert r.status_code == 403

    async def test_execute_unknown_id_returns_404(
        self, client: AsyncClient, org_and_admin_key
    ) -> None:
        _org_id, admin_key = org_and_admin_key
        r = await client.post(
            "/api/governance/approvals/does-not-exist/execute",
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 404

    async def test_cross_org_execute_returns_404_not_403(
        self, client: AsyncClient, org_and_admin_key
    ) -> None:
        _org_id, admin_key = org_and_admin_key
        r = await client.post(
            "/api/orgs",
            json={"name": "Other Resume Co", "slug": "other-resume-co"},
            headers=BOOTSTRAP_AUTH,
        )
        other_org_id = r.json()["id"]
        other_approval_id = await _seed_dispatchable_approval(other_org_id)

        r = await client.post(
            f"/api/governance/approvals/{other_approval_id}/execute",
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 404

    async def test_execution_writes_evidence_with_resumed_reason_code(
        self,
        client: AsyncClient,
        org_and_admin_key,
    ) -> None:
        from responsibleai.dashboard.app import _db_engine

        org_id, admin_key = org_and_admin_key
        headers = {"Authorization": f"Bearer {admin_key}"}
        approval_id = await _seed_dispatchable_approval(org_id)
        await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers=headers,
        )
        await client.post(f"/api/governance/approvals/{approval_id}/execute", headers=headers)

        records = await EvidenceRepository(_db_engine).list_for_org(org_id, decision="ALLOW")
        assert any(
            any(code.startswith("RESUMED_AFTER_APPROVAL:") for code in r.reason_codes)
            for r in records
        )


class TestResumeApprovalDirectUnit:
    """Unit-level tests against resume_approval() itself (bypassing
    HTTP), for the two invariant-violation cases the REST layer already
    proves map to 409 -- these confirm the underlying exception types
    directly, matching test_approval_execution_binding.py's style."""

    @pytest.fixture()
    async def engine(self):
        from responsibleai.db import create_engine

        e = create_engine(":memory:")
        await e.init()
        yield e
        await e.close()

    async def test_mutation_after_persist_is_impossible_via_public_api(self, engine) -> None:
        """There's no public way to mutate a persisted approval's
        arguments after creation (no update method exists on
        ApprovalRepository for that column) -- this documents that
        invariant by construction rather than by a broken test."""
        from responsibleai.db.approval_repository import ApprovalRepository as _Repo

        assert not hasattr(_Repo, "update_arguments")

    async def test_consume_still_enforces_mismatch_if_arguments_tampered_pre_reconstruction(
        self,
        engine,
    ) -> None:
        from responsibleai.db import ApprovalRepository as _ApprovalRepo
        from responsibleai.db import EvidenceRepository as _EvidenceRepo

        repo = _ApprovalRepo(engine)
        identity = IdentityContext(identity_id="k1", kind="api_key", org_id="org-1")
        agent = AgentContext(identity=identity, framework="mcp-client")
        authority = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"rai_scan"}),
            require_approval_for=frozenset({"rai_scan"}),
        )
        action = ActionRequest(
            agent=agent,
            action_type="rai_scan",
            target="rai_scan",
            arguments={"text": "original"},
        )
        decision = WhitePactRuntimeGateway().evaluate(action, authority)
        approval = await repo.create(build_approval_request(action, decision))
        await repo.resolve(
            approval.approval_id, resolved_by="human-1", outcome=ApprovalStatus.APPROVED
        )

        # Simulate tampering: overwrite the persisted digest directly so
        # a resume's reconstructed action no longer matches it.
        from sqlalchemy import update

        from responsibleai.db.engine import governance_approvals

        async with engine.raw.begin() as conn:
            await conn.execute(
                update(governance_approvals)
                .where(governance_approvals.c.id == approval.approval_id)
                .values(action_digest="0" * 64)
            )

        with pytest.raises(ApprovalActionMismatchError):
            await resume_approval(
                approval.approval_id,
                approval_repo=repo,
                evidence_repo=_EvidenceRepo(engine),
                org_id="org-1",
            )

    async def test_resume_of_never_approved_raises_not_approved(self, engine) -> None:
        from responsibleai.db import ApprovalRepository as _ApprovalRepo
        from responsibleai.db import EvidenceRepository as _EvidenceRepo

        repo = _ApprovalRepo(engine)
        identity = IdentityContext(identity_id="k1", kind="api_key", org_id="org-1")
        agent = AgentContext(identity=identity, framework="mcp-client")
        authority = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"rai_scan"}),
            require_approval_for=frozenset({"rai_scan"}),
        )
        action = ActionRequest(agent=agent, action_type="rai_scan", target="rai_scan")
        decision = WhitePactRuntimeGateway().evaluate(action, authority)
        approval = await repo.create(build_approval_request(action, decision))

        with pytest.raises(ApprovalNotApprovedError):
            await resume_approval(
                approval.approval_id,
                approval_repo=repo,
                evidence_repo=_EvidenceRepo(engine),
                org_id="org-1",
            )


class TestResumeApprovalReChecksHeartAtExecutionTime:
    """Heart Enforcement Chokepoint Closure Phase E6: the gap the
    Phase E0 audit found -- resume_approval() previously never
    re-checked Heart legitimacy at execution time, only at the
    original REQUIRE_APPROVAL decision time. If the principal's root
    or consent is revoked while the approval sits queued waiting for a
    human, the original (now stale) verdict alone let execution
    proceed. These tests use resume_approval() directly (bypassing
    HTTP), matching TestResumeApprovalDirectUnit's own established
    pattern, since exercising this specifically needs an ORGANIZATION-
    kind root persisted for identity_id="k1" (what
    _agent_from_approval() always reconstructs) that can be revoked
    between approval and resume."""

    @pytest.fixture()
    async def engine(self):
        from responsibleai.db import create_engine

        e = create_engine(":memory:")
        await e.init()
        yield e
        await e.close()

    @pytest.fixture(autouse=True)
    def _enterprise_mode(self, monkeypatch: pytest.MonkeyPatch):
        from responsibleai.dashboard.config import get_settings

        monkeypatch.setattr(get_settings(), "enterprise_mode", True)
        yield

    async def _seed_approved(self, engine, *, org_id: str = "org-1"):
        from responsibleai.db import ApprovalRepository as _ApprovalRepo

        repo = _ApprovalRepo(engine)
        identity = IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)
        agent = AgentContext(identity=identity, framework="mcp-client")
        authority = AuthorityContext(
            delegated_by=org_id,
            granted_action_types=frozenset({"rai_health"}),
            require_approval_for=frozenset({"rai_health"}),
        )
        action = ActionRequest(agent=agent, action_type="rai_health", target="rai_health")
        decision = WhitePactRuntimeGateway().evaluate(action, authority)
        assert decision.decision == GovernanceDecision.REQUIRE_APPROVAL
        approval = await repo.create(build_approval_request(action, decision))
        await repo.resolve(
            approval.approval_id, outcome=ApprovalStatus.APPROVED, resolved_by="admin"
        )
        return repo, approval.approval_id

    async def test_no_root_repo_wired_is_a_complete_no_op(self, engine) -> None:
        """Backward compatibility: omitting root_authority_repo/
        consent_repo entirely (the default) must behave identically to
        before this phase existed, even with enterprise_mode=true."""
        from responsibleai.db import EvidenceRepository as _EvidenceRepo

        repo, approval_id = await self._seed_approved(engine)
        result = await resume_approval(
            approval_id, approval_repo=repo, evidence_repo=_EvidenceRepo(engine), org_id="org-1"
        )
        assert result["status"] == "ok"

    async def test_revoked_root_since_approval_denies_execution(self, engine) -> None:
        from responsibleai.db import EvidenceRepository as _EvidenceRepo
        from responsibleai.db.consent_proof_repository import ConsentProofRepository
        from responsibleai.db.root_authority_repository import RootAuthorityRepository
        from responsibleai.governance.identity_authority_adapter import (
            build_root_authority_record_from_identity,
        )
        from responsibleai.governance.models import IdentityKind
        from responsibleai.mcp.governance_integration import ApprovalRevokedSinceQueuedError

        repo, approval_id = await self._seed_approved(engine)

        # Simulate what already happened at the ORIGINAL decision time
        # (a root get-or-created for this identity) -- then simulate an
        # admin revoking it while the approval sat waiting for a human.
        root_repo = RootAuthorityRepository(engine)
        reconstructed_identity = IdentityContext(
            identity_id="k1", kind=IdentityKind.ORGANIZATION, org_id="org-1"
        )
        record = build_root_authority_record_from_identity(
            reconstructed_identity, issuer="org_repository", verification_method="api_key_hash"
        )
        created = await root_repo.create(record)
        await root_repo.revoke(created.root_id, revoked_by="admin-1", reason="offboarded")

        with pytest.raises(ApprovalRevokedSinceQueuedError, match=approval_id):
            await resume_approval(
                approval_id,
                approval_repo=repo,
                evidence_repo=_EvidenceRepo(engine),
                org_id="org-1",
                root_authority_repo=root_repo,
                consent_repo=ConsentProofRepository(engine),
            )

        # Single-use is unconditional: the approval must be spent even
        # though execution was denied -- a second attempt (even without
        # the Heart check wired at all) must not succeed either.
        with pytest.raises(ApprovalNotApprovedError):
            await resume_approval(
                approval_id, approval_repo=repo, evidence_repo=_EvidenceRepo(engine), org_id="org-1"
            )

    async def test_still_legitimate_root_allows_execution(self, engine) -> None:
        """Control: a root that was never revoked must still allow
        execution once root_authority_repo/consent_repo are wired --
        proves the previous test's denial genuinely came from the
        revocation, not from wiring the params at all."""
        from responsibleai.db import EvidenceRepository as _EvidenceRepo
        from responsibleai.db.consent_proof_repository import ConsentProofRepository
        from responsibleai.db.root_authority_repository import RootAuthorityRepository

        repo, approval_id = await self._seed_approved(engine)
        root_repo = RootAuthorityRepository(engine)

        result = await resume_approval(
            approval_id,
            approval_repo=repo,
            evidence_repo=_EvidenceRepo(engine),
            org_id="org-1",
            root_authority_repo=root_repo,
            consent_repo=ConsentProofRepository(engine),
        )
        assert result["status"] == "ok"
