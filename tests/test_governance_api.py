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
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as c:
            yield c


@pytest.fixture()
async def org_and_admin_key(client: AsyncClient):
    r = await client.post(
        "/api/orgs",
        json={"name": "Governance Test Co", "slug": "governance-test-co"},
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


@pytest.fixture()
async def org_and_analyst_key(client: AsyncClient, org_and_admin_key):
    org_id, _admin_key = org_and_admin_key
    r = await client.post(
        f"/api/orgs/{org_id}/keys",
        json={"name": "analyst-key", "role": "ANALYST"},
        headers=BOOTSTRAP_AUTH,
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
    authority = AuthorityContext(
        delegated_by=org_id, granted_action_types=frozenset({"mcp_tool_call"})
    )
    action = ActionRequest(agent=agent, action_type="mcp_tool_call", target=decision_target)
    decision = gw.evaluate(action, authority)
    await EvidenceRepository(_db_engine).record(
        build_evidence_record(action, agent, authority, decision)
    )


async def _seed_approval(org_id: str) -> str:
    from responsibleai.dashboard.app import _db_engine

    gw = WhitePactRuntimeGateway()
    identity = IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)
    agent = AgentContext(identity=identity, framework="mcp-client")
    authority = AuthorityContext(
        delegated_by=org_id,
        granted_action_types=frozenset({"deployment"}),
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

    async def test_list_evidence_returns_seeded_records(
        self, client: AsyncClient, org_and_analyst_key
    ) -> None:
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

    async def test_verify_evidence_true_when_clean(
        self, client: AsyncClient, org_and_analyst_key
    ) -> None:
        org_id, key = org_and_analyst_key
        await _seed_evidence(org_id)
        r = await client.get(
            "/api/governance/evidence/verify", headers={"Authorization": f"Bearer {key}"}
        )
        assert r.status_code == 200
        assert r.json() == {"org_id": org_id, "chain_intact": True}

    async def test_evidence_scoped_to_caller_org_not_visible_across_orgs(
        self,
        client: AsyncClient,
        org_and_analyst_key,
    ) -> None:
        org_id, key = org_and_analyst_key
        await _seed_evidence(org_id)

        r = await client.post(
            "/api/orgs",
            json={"name": "Other Co", "slug": "other-co"},
            headers=BOOTSTRAP_AUTH,
        )
        other_org_id = r.json()["id"]
        r = await client.post(
            f"/api/orgs/{other_org_id}/keys",
            json={"name": "k", "role": "ANALYST"},
            headers=BOOTSTRAP_AUTH,
        )
        other_key = r.json()["key"]

        r = await client.get(
            "/api/governance/evidence", headers={"Authorization": f"Bearer {other_key}"}
        )
        assert r.json()["evidence"] == []


class TestApprovalEndpoints:
    async def test_list_pending_empty(self, client: AsyncClient, org_and_analyst_key) -> None:
        _org_id, key = org_and_analyst_key
        r = await client.get(
            "/api/governance/approvals", headers={"Authorization": f"Bearer {key}"}
        )
        assert r.status_code == 200
        assert r.json() == {"pending": [], "limit": 50}

    async def test_list_pending_returns_seeded_approval(
        self, client: AsyncClient, org_and_analyst_key
    ) -> None:
        org_id, key = org_and_analyst_key
        await _seed_approval(org_id)
        r = await client.get(
            "/api/governance/approvals", headers={"Authorization": f"Bearer {key}"}
        )
        body = r.json()
        assert len(body["pending"]) == 1
        assert body["pending"][0]["status"] == "PENDING"
        assert body["pending"][0]["target"] == "prod"

    async def test_resolve_requires_admin_role(
        self, client: AsyncClient, org_and_analyst_key
    ) -> None:
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
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers=headers,
        )
        r = await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "DENIED"},
            headers=headers,
        )
        assert r.status_code == 409

    async def test_resolve_unknown_id_returns_404(
        self, client: AsyncClient, org_and_admin_key
    ) -> None:
        _org_id, admin_key = org_and_admin_key
        r = await client.post(
            "/api/governance/approvals/does-not-exist/resolve",
            json={"outcome": "APPROVED"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 404

    async def test_resolve_other_orgs_approval_returns_404_not_403(
        self,
        client: AsyncClient,
        org_and_admin_key,
    ) -> None:
        """Cross-org access must not leak *anything*, including whether
        the ID exists -- 404, never 403, for another org's approval."""
        _org_id, admin_key = org_and_admin_key

        r = await client.post(
            "/api/orgs",
            json={"name": "Other Co 2", "slug": "other-co-2"},
            headers=BOOTSTRAP_AUTH,
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
        self,
        client: AsyncClient,
        org_and_admin_key,
    ) -> None:
        org_id, admin_key = org_and_admin_key
        approval_id = await _seed_approval(org_id)
        r = await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "MAYBE"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 422


async def _seed_quorum_approval(org_id: str, *, required_approvals: int = 2) -> str:
    """Same shape as _seed_approval() above, but with a caller-chosen
    required_approvals -- REST-level proof of the quorum feature
    (governance/approval.py's default_required_approvals(), Task #142)
    on top of test_approval_quorum.py's repository-level coverage."""
    from responsibleai.dashboard.app import _db_engine

    gw = WhitePactRuntimeGateway()
    identity = IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)
    agent = AgentContext(identity=identity, framework="mcp-client")
    authority = AuthorityContext(
        delegated_by=org_id,
        granted_action_types=frozenset({"deployment"}),
        require_approval_for=frozenset({"deployment"}),
    )
    action = ActionRequest(agent=agent, action_type="deployment", target="prod")
    decision = gw.evaluate(action, authority)
    approval = build_approval_request(action, decision)
    approval.required_approvals = required_approvals
    saved = await ApprovalRepository(_db_engine).create(approval)
    return saved.approval_id


class TestApprovalQuorumEndpoints:
    async def test_single_admin_vote_leaves_approval_pending(
        self,
        client: AsyncClient,
        org_and_admin_key,
    ) -> None:
        org_id, admin_key = org_and_admin_key
        approval_id = await _seed_quorum_approval(org_id, required_approvals=2)
        r = await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "PENDING"
        assert r.json()["required_approvals"] == 2

    async def test_second_distinct_admin_reaches_quorum(
        self,
        client: AsyncClient,
        org_and_admin_key,
    ) -> None:
        org_id, admin_key = org_and_admin_key
        approval_id = await _seed_quorum_approval(org_id, required_approvals=2)

        r = await client.post(
            f"/api/orgs/{org_id}/keys",
            json={"name": "second-admin", "role": "ADMIN"},
            headers=BOOTSTRAP_AUTH,
        )
        second_admin_key = r.json()["key"]

        await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        r2 = await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers={"Authorization": f"Bearer {second_admin_key}"},
        )
        assert r2.status_code == 200
        assert r2.json()["status"] == "APPROVED"

    async def test_double_vote_from_same_admin_returns_409(
        self,
        client: AsyncClient,
        org_and_admin_key,
    ) -> None:
        org_id, admin_key = org_and_admin_key
        approval_id = await _seed_quorum_approval(org_id, required_approvals=2)
        headers = {"Authorization": f"Bearer {admin_key}"}
        await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers=headers,
        )
        r = await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers=headers,
        )
        assert r.status_code == 409

    async def test_votes_endpoint_lists_history(
        self, client: AsyncClient, org_and_admin_key
    ) -> None:
        org_id, admin_key = org_and_admin_key
        approval_id = await _seed_quorum_approval(org_id, required_approvals=2)
        headers = {"Authorization": f"Bearer {admin_key}"}
        await client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED", "notes": "first vote"},
            headers=headers,
        )

        r = await client.get(f"/api/governance/approvals/{approval_id}/votes", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["required_approvals"] == 2
        assert len(body["votes"]) == 1
        assert body["votes"][0]["notes"] == "first vote"

    async def test_votes_endpoint_cross_org_returns_404(
        self, client: AsyncClient, org_and_admin_key
    ) -> None:
        _org_id, admin_key = org_and_admin_key
        r = await client.post(
            "/api/orgs",
            json={"name": "Other Quorum Co", "slug": "other-quorum-co"},
            headers=BOOTSTRAP_AUTH,
        )
        other_org_id = r.json()["id"]
        other_approval_id = await _seed_quorum_approval(other_org_id)

        r = await client.get(
            f"/api/governance/approvals/{other_approval_id}/votes",
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 404


class TestSupplyChainScanEndpoint:
    async def test_scan_requires_auth(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/governance/supplychain/scan",
            json={"server_name": "acme-tools"},
        )
        assert r.status_code == 401

    async def test_clean_manifest_returns_findings_list(
        self, client: AsyncClient, org_and_analyst_key
    ) -> None:
        _org_id, key = org_and_analyst_key
        r = await client.post(
            "/api/governance/supplychain/scan",
            json={
                "server_name": "acme-tools",
                "publisher": "Acme Inc",
                "tools": [{"name": "search_web", "description": "Search the web."}],
                "check_known_incidents": False,
            },
            headers={"Authorization": f"Bearer {key}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["server_name"] == "acme-tools"
        assert isinstance(body["findings"], list)
        assert not any(k in body for k in ("score", "trust_score", "rating"))
        checks = {f["check"] for f in body["findings"]}
        assert checks == {"confusable_characters", "tool_description_scan"}

    async def test_incident_check_included_by_default(
        self, client: AsyncClient, org_and_analyst_key
    ) -> None:
        _org_id, key = org_and_analyst_key
        r = await client.post(
            "/api/governance/supplychain/scan",
            json={"server_name": "acme-tools"},
            headers={"Authorization": f"Bearer {key}"},
        )
        assert r.status_code == 200
        checks = {f["check"] for f in r.json()["findings"]}
        assert "known_incidents" in checks

    async def test_confusable_server_name_flagged(
        self, client: AsyncClient, org_and_analyst_key
    ) -> None:
        _org_id, key = org_and_analyst_key
        r = await client.post(
            "/api/governance/supplychain/scan",
            json={"server_name": "rаi_tools", "check_known_incidents": False},  # Cyrillic а
            headers={"Authorization": f"Bearer {key}"},
        )
        finding = next(f for f in r.json()["findings"] if f["check"] == "confusable_characters")
        assert finding["verdict"] == "VERIFIED_FACT"
        assert "server_name" in finding["detail"]["matches"]

    async def test_empty_server_name_rejected_by_validation(
        self, client: AsyncClient, org_and_analyst_key
    ) -> None:
        _org_id, key = org_and_analyst_key
        r = await client.post(
            "/api/governance/supplychain/scan",
            json={"server_name": ""},
            headers={"Authorization": f"Bearer {key}"},
        )
        assert r.status_code == 422


class TestPolicyEndpoints:
    async def test_get_policy_empty_for_new_org(
        self, client: AsyncClient, org_and_analyst_key
    ) -> None:
        _org_id, key = org_and_analyst_key
        r = await client.get("/api/governance/policy", headers={"Authorization": f"Bearer {key}"})
        assert r.status_code == 200
        assert r.json()["rules"] == []

    async def test_analyst_cannot_add_rule(self, client: AsyncClient, org_and_analyst_key) -> None:
        _org_id, key = org_and_analyst_key
        r = await client.post(
            "/api/governance/policy/rules",
            json={"rule_id": "r1", "reason_code": "test", "effect": "DENY"},
            headers={"Authorization": f"Bearer {key}"},
        )
        assert r.status_code == 403

    async def test_admin_adds_rule(self, client: AsyncClient, org_and_admin_key) -> None:
        org_id, admin_key = org_and_admin_key
        r = await client.post(
            "/api/governance/policy/rules",
            json={
                "rule_id": "block-deployment",
                "reason_code": "no_prod_deploys_without_review",
                "effect": "REQUIRE_APPROVAL",
                "action_types": ["deployment"],
            },
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["rule_id"] == "block-deployment"
        assert body["effect"] == "REQUIRE_APPROVAL"
        assert body["action_types"] == ["deployment"]

        r = await client.get(
            "/api/governance/policy", headers={"Authorization": f"Bearer {admin_key}"}
        )
        assert [rule["rule_id"] for rule in r.json()["rules"]] == ["block-deployment"]

    async def test_duplicate_rule_id_rejected(self, client: AsyncClient, org_and_admin_key) -> None:
        _org_id, admin_key = org_and_admin_key
        body = {"rule_id": "r1", "reason_code": "test", "effect": "DENY"}
        r1 = await client.post(
            "/api/governance/policy/rules",
            json=body,
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r1.status_code == 200
        r2 = await client.post(
            "/api/governance/policy/rules",
            json=body,
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r2.status_code == 409

    async def test_invalid_effect_rejected_by_validation(
        self, client: AsyncClient, org_and_admin_key
    ) -> None:
        _org_id, admin_key = org_and_admin_key
        r = await client.post(
            "/api/governance/policy/rules",
            json={"rule_id": "r1", "reason_code": "test", "effect": "QUARANTINE"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        # QUARANTINE is a real GovernanceDecision but not a valid *rule*
        # effect (see governance/policy.py's _RULE_EFFECTS) — rejected at
        # the request-schema level (pattern match), same layer that
        # rejects any other unrecognized string.
        assert r.status_code == 422

    async def test_remove_rule(self, client: AsyncClient, org_and_admin_key) -> None:
        _org_id, admin_key = org_and_admin_key
        await client.post(
            "/api/governance/policy/rules",
            json={"rule_id": "r1", "reason_code": "test", "effect": "DENY"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        r = await client.delete(
            "/api/governance/policy/rules/r1",
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 200
        r = await client.get(
            "/api/governance/policy", headers={"Authorization": f"Bearer {admin_key}"}
        )
        assert r.json()["rules"] == []

    async def test_remove_unknown_rule_returns_404(
        self, client: AsyncClient, org_and_admin_key
    ) -> None:
        _org_id, admin_key = org_and_admin_key
        r = await client.delete(
            "/api/governance/policy/rules/does-not-exist",
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 404

    async def test_reorder_rules(self, client: AsyncClient, org_and_admin_key) -> None:
        _org_id, admin_key = org_and_admin_key
        headers = {"Authorization": f"Bearer {admin_key}"}
        for rid in ("r1", "r2", "r3"):
            await client.post(
                "/api/governance/policy/rules",
                json={"rule_id": rid, "reason_code": "test", "effect": "DENY"},
                headers=headers,
            )
        r = await client.post(
            "/api/governance/policy/reorder",
            json={"rule_ids": ["r3", "r1", "r2"]},
            headers=headers,
        )
        assert r.status_code == 200
        assert [rule["rule_id"] for rule in r.json()["rules"]] == ["r3", "r1", "r2"]

    async def test_policy_scoped_to_caller_org_not_visible_across_orgs(
        self,
        client: AsyncClient,
        org_and_admin_key,
    ) -> None:
        org_id, admin_key = org_and_admin_key
        await client.post(
            "/api/governance/policy/rules",
            json={"rule_id": "org-a-secret-rule", "reason_code": "test", "effect": "DENY"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )

        r = await client.post(
            "/api/orgs",
            json={"name": "Other Policy Co", "slug": "other-policy-co"},
            headers=BOOTSTRAP_AUTH,
        )
        other_org_id = r.json()["id"]
        r = await client.post(
            f"/api/orgs/{other_org_id}/keys",
            json={"name": "k", "role": "ADMIN"},
            headers=BOOTSTRAP_AUTH,
        )
        other_key = r.json()["key"]

        r = await client.get(
            "/api/governance/policy", headers={"Authorization": f"Bearer {other_key}"}
        )
        assert r.json()["rules"] == []


@pytest.fixture()
async def org_and_owner_key(client: AsyncClient):
    r = await client.post(
        "/api/orgs",
        json={"name": "Ceiling Test Co", "slug": "ceiling-test-co"},
        headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    org_id = r.json()["id"]
    r = await client.post(
        f"/api/orgs/{org_id}/keys",
        json={"name": "owner-key", "role": "OWNER"},
        headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    return org_id, r.json()["key"]


class TestAuthorityCeilingEndpoints:
    async def test_get_ceiling_all_null_for_new_org(
        self, client: AsyncClient, org_and_admin_key
    ) -> None:
        org_id, admin_key = org_and_admin_key
        r = await client.get(
            f"/api/orgs/{org_id}/authority-ceiling",
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["org_id"] == org_id
        assert body["max_value_usd"] is None
        assert body["allowed_targets"] is None
        assert body["require_approval_for"] == []

    async def test_analyst_cannot_view_ceiling(
        self, client: AsyncClient, org_and_analyst_key
    ) -> None:
        _org_id, key = org_and_analyst_key
        org_id = _org_id
        r = await client.get(
            f"/api/orgs/{org_id}/authority-ceiling",
            headers={"Authorization": f"Bearer {key}"},
        )
        assert r.status_code == 403

    async def test_admin_cannot_set_ceiling(self, client: AsyncClient, org_and_admin_key) -> None:
        """Setting the ceiling requires OWNER, not just ADMIN -- an
        org-wide authority cap is a more consequential change than
        adding a policy rule (which ADMIN can already do)."""
        org_id, admin_key = org_and_admin_key
        r = await client.put(
            f"/api/orgs/{org_id}/authority-ceiling",
            json={"max_value_usd": 500_000},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 403

    async def test_owner_sets_and_gets_ceiling(
        self, client: AsyncClient, org_and_owner_key
    ) -> None:
        org_id, owner_key = org_and_owner_key
        r = await client.put(
            f"/api/orgs/{org_id}/authority-ceiling",
            json={
                "max_value_usd": 500_000,
                "allowed_targets": ["payment_*"],
                "require_approval_for": ["payment.execute"],
            },
            headers={"Authorization": f"Bearer {owner_key}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["max_value_usd"] == 500_000
        assert body["allowed_targets"] == ["payment_*"]
        assert body["require_approval_for"] == ["payment.execute"]

        r = await client.get(
            f"/api/orgs/{org_id}/authority-ceiling",
            headers={"Authorization": f"Bearer {owner_key}"},
        )
        assert r.json()["max_value_usd"] == 500_000

    async def test_set_ceiling_replaces_wholesale(
        self, client: AsyncClient, org_and_owner_key
    ) -> None:
        org_id, owner_key = org_and_owner_key
        await client.put(
            f"/api/orgs/{org_id}/authority-ceiling",
            json={"max_value_usd": 500_000, "allowed_targets": ["payment_*"]},
            headers={"Authorization": f"Bearer {owner_key}"},
        )
        r = await client.put(
            f"/api/orgs/{org_id}/authority-ceiling",
            json={"max_value_usd": 100_000},
            headers={"Authorization": f"Bearer {owner_key}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["max_value_usd"] == 100_000
        assert body["allowed_targets"] is None  # not re-sent -> cleared, not preserved

    async def test_negative_max_value_usd_rejected(
        self, client: AsyncClient, org_and_owner_key
    ) -> None:
        org_id, owner_key = org_and_owner_key
        r = await client.put(
            f"/api/orgs/{org_id}/authority-ceiling",
            json={"max_value_usd": -1},
            headers={"Authorization": f"Bearer {owner_key}"},
        )
        assert r.status_code == 422
