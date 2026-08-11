"""End-to-end HTTP tests for the /api/governance/* endpoints (evidence
listing/verification, approval listing/resolution) against a real
auth-enabled app instance — see test_mfa_login_flow.py's module
docstring for why auth is forced on by monkeypatching the settings
singleton here rather than via os.environ.
"""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.db import ApprovalRepository, EvidenceRepository
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.approval import build_approval_request
from responsibleai.governance.evidence import build_evidence_record

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
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as c:
            yield c


@pytest.fixture()
async def org_and_admin_key(client: AsyncClient):
    r = await client.post(
        "/api/orgs", json={"name": "Governance Test Co", "slug": "governance-test-co"}, headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    org_id = r.json()["id"]

    r = await client.post(
        f"/api/orgs/{org_id}/keys", json={"name": "admin-key", "role": "ADMIN"}, headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    return org_id, r.json()["key"]


@pytest.fixture()
async def org_and_analyst_key(client: AsyncClient, org_and_admin_key):
    org_id, _admin_key = org_and_admin_key
    r = await client.post(
        f"/api/orgs/{org_id}/keys", json={"name": "analyst-key", "role": "ANALYST"}, headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    return org_id, r.json()["key"]


async def _seed_evidence(org_id: str, *, decision_target: str = "rai_health") -> None:
    """Seeds data by writing directly through the running app's own
    `_db_engine` module global (imported fresh here since the lifespan
    sets it after this test module is first imported) -- a repository
    bound to that exact engine object, not a second, separate one."""
    from responsibleai.dashboard.app import _db_engine

    gw = WhitePactRuntimeGateway()
    identity = IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)
    agent = AgentContext(identity=identity, framework="mcp-client")
    authority = AuthorityContext(delegated_by=org_id, granted_action_types=frozenset({"mcp_tool_call"}))
    action = ActionRequest(agent=agent, action_type="mcp_tool_call", target=decision_target)
    decision = gw.evaluate(action, authority)
    await EvidenceRepository(_db_engine).record(build_evidence_record(action, agent, authority, decision))


async def _seed_approval(org_id: str) -> str:
    from responsibleai.dashboard.app import _db_engine

    gw = WhitePactRuntimeGateway()
    identity = IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)
    agent = AgentContext(identity=identity, framework="mcp-client")
    authority = AuthorityContext(
        delegated_by=org_id, granted_action_types=frozenset({"deployment"}),
        require_approval_for=frozenset({"deployment"}),
    )
    action = ActionRequest(agent=agent, action_type="deployment", target="prod")
    decision = gw.evaluate(action, authority)
    saved = await ApprovalRepository(_db_engine).create(build_approval_request(action, decision))
    return saved.approval_id


class TestEvidenceEndpoints:
    async def test_list_evidence_empty(self, client: AsyncClient, org_and_analyst_key) -> None:
        _org_id, key = org_and_analyst_key
        r = await client.get("/api/governance/evidence", headers={"Authorization": f"Bearer {key}"})
        assert r.status_code == 200
        assert r.json() == {"evidence": [], "limit": 50}

    async def test_list_evidence_returns_seeded_records(self, client: AsyncClient, org_and_analyst_key) -> None:
        org_id, key = org_and_analyst_key
        await _seed_evidence(org_id)
        r = await client.get("/api/governance/evidence", headers={"Authorization": f"Bearer {key}"})
        assert r.status_code == 200
        body = r.json()
        assert len(body["evidence"]) == 1
        assert body["evidence"][0]["decision"] == "ALLOW"
        assert body["evidence"][0]["organization_id"] == org_id

    async def test_list_evidence_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/governance/evidence")
        assert r.status_code == 401

    async def test_verify_evidence_true_when_clean(self, client: AsyncClient, org_and_analyst_key) -> None:
        org_id, key = org_and_analyst_key
        await _seed_evidence(org_id)
        r = await client.get("/api/governance/evidence/verify", headers={"Authorization": f"Bearer {key}"})
        assert r.status_code == 200
        assert r.json() == {"org_id": org_id, "chain_intact": True}

    async def test_evidence_scoped_to_caller_org_not_visible_across_orgs(
        self, client: AsyncClient, org_and_analyst_key,
    ) -> None:
        org_id, key = org_and_analyst_key
        await _seed_evidence(org_id)

        r = await client.post(
            "/api/orgs", json={"name": "Other Co", "slug": "other-co"}, headers=BOOTSTRAP_AUTH,
        )
        other_org_id = r.json()["id"]
        r = await client.post(
            f"/api/orgs/{other_org_id}/keys", json={"name": "k", "role": "ANALYST"}, headers=BOOTSTRAP_AUTH,
        )
        other_key = r.json()["key"]

        r = await client.get("/api/governance/evidence", headers={"Authorization": f"Bearer {other_key}"})
        assert r.json()["evidence"] == []


class TestApprovalEndpoints:
    async def test_list_pending_empty(self, client: AsyncClient, org_and_analyst_key) -> None:
        _org_id, key = org_and_analyst_key
        r = await client.get("/api/governance/approvals", headers={"Authorization": f"Bearer {key}"})
        assert r.status_code == 200
        assert r.json() == {"pending": [], "limit": 50}

    async def test_list_pending_returns_seeded_approval(self, client: AsyncClient, org_and_analyst_key) -> None:
        org_id, key = org_and_analyst_key
        await _seed_approval(org_id)
        r = await client.get("/api/governance/approvals", headers={"Authorization": f"Bearer {key}"})
        body = r.json()
        assert len(body["pending"]) == 1
        assert body["pending"][0]["status"] == "PENDING"
        assert body["pending"][0]["target"] == "prod"

    async def test_resolve_requires_admin_role(self, client: AsyncClient, org_and_analyst_key) -> None:
        org_id, analyst_key = org_and_analyst_key
        approval_id = await _seed_approval(org_id)
        r = await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers={"Authorization": f"Bearer {analyst_key}"},
        )
        assert r.status_code == 403

    async def test_resolve_approved_by_admin(self, client: AsyncClient, org_and_admin_key) -> None:
        org_id, admin_key = org_and_admin_key
        approval_id = await _seed_approval(org_id)
        r = await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED", "notes": "looks fine"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "APPROVED"
        assert body["resolution_notes"] == "looks fine"

    async def test_double_resolve_returns_409(self, client: AsyncClient, org_and_admin_key) -> None:
        org_id, admin_key = org_and_admin_key
        approval_id = await _seed_approval(org_id)
        headers = {"Authorization": f"Bearer {admin_key}"}
        await client.post(
            f"/api/governance/approvals/{approval_id}/resolve", json={"outcome": "APPROVED"}, headers=headers,
        )
        r = await client.post(
            f"/api/governance/approvals/{approval_id}/resolve", json={"outcome": "DENIED"}, headers=headers,
        )
        assert r.status_code == 409

    async def test_resolve_unknown_id_returns_404(self, client: AsyncClient, org_and_admin_key) -> None:
        _org_id, admin_key = org_and_admin_key
        r = await client.post(
            "/api/governance/approvals/does-not-exist/resolve",
            json={"outcome": "APPROVED"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 404

    async def test_resolve_other_orgs_approval_returns_404_not_403(
        self, client: AsyncClient, org_and_admin_key,
    ) -> None:
        """Cross-org access must not leak *anything*, including whether
        the ID exists -- 404, never 403, for another org's approval."""
        _org_id, admin_key = org_and_admin_key

        r = await client.post(
            "/api/orgs", json={"name": "Other Co 2", "slug": "other-co-2"}, headers=BOOTSTRAP_AUTH,
        )
        other_org_id = r.json()["id"]
        other_approval_id = await _seed_approval(other_org_id)

        r = await client.post(
            f"/api/governance/approvals/{other_approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 404

    async def test_resolve_invalid_outcome_rejected_by_validation(
        self, client: AsyncClient, org_and_admin_key,
    ) -> None:
        org_id, admin_key = org_and_admin_key
        approval_id = await _seed_approval(org_id)
        r = await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "MAYBE"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 422
