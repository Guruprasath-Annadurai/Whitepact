# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-2 live governed execution invalidation (approval, policy, delegation, binding)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.db import PolicyRepository
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.rbac.models import Role
from tests.org_http_fixtures import seed_org_with_key
from tests.test_mcp_governance_dispatch import _call
from tests.test_resume_after_approval import _seed_dispatchable_approval

pytest_plugins = ("tests.test_mcp_governance_dispatch",)


@pytest.fixture(autouse=True)
def _auth_and_db(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    limiter.reset()
    yield


@pytest.fixture()
async def governance_client():
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            yield client


def _dispatch_spy(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    dispatch = AsyncMock(return_value={"status": "ok"})
    monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", dispatch)
    return dispatch


class TestLiveMcpPolicyInvalidation:
    async def test_deny_rule_blocks_before_dispatch(
        self, governed_app, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app_, raw_key, org_id, engine = governed_app
        await PolicyRepository(engine).add_rule(
            org_id,
            PolicyRule(
                rule_id="ws2-deny-health",
                reason_code="POLICY_DENY_HEALTH",
                effect=GovernanceDecision.DENY,
                action_types=frozenset({"rai_health"}),
            ),
        )
        dispatch = _dispatch_spy(monkeypatch)
        result = await _call(app_, raw_key, "rai_health", {})
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_denied"
        dispatch.assert_not_awaited()

    async def test_require_approval_added_blocks_immediate_dispatch(
        self, governed_app, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app_, raw_key, org_id, engine = governed_app
        await PolicyRepository(engine).add_rule(
            org_id,
            PolicyRule(
                rule_id="ws2-require-scan",
                reason_code="POLICY_REQUIRE_SCAN",
                effect=GovernanceDecision.REQUIRE_APPROVAL,
                action_types=frozenset({"rai_scan"}),
            ),
        )
        dispatch = _dispatch_spy(monkeypatch)
        result = await _call(
            app_,
            raw_key,
            "rai_scan",
            {"text": "hello world"},
        )
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_approval_required"
        dispatch.assert_not_awaited()

    async def test_policy_version_drift_after_approval_before_execute(
        self, governance_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from responsibleai.dashboard.app import _db_engine
        from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository

        org_id, _kid, admin_key = await seed_org_with_key(
            name="Policy Drift Co",
            slug=f"policy-drift-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        headers = {"Authorization": f"Bearer {admin_key}"}
        approval_id = await _seed_dispatchable_approval(org_id)
        await governance_client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers=headers,
        )
        await RevocationEpochRepository(_db_engine).bump(org_id)
        dispatch = _dispatch_spy(monkeypatch)
        response = await governance_client.post(
            f"/api/governance/approvals/{approval_id}/execute",
            headers=headers,
        )
        assert response.status_code == 409
        dispatch.assert_not_awaited()


class TestLiveMcpDelegationInvalidation:
    async def test_revoked_delegation_never_dispatches(
        self, governed_app_with_key, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from responsibleai.db import DelegationRepository

        app_, raw_key, org_id, engine, key_id = governed_app_with_key
        await DelegationRepository(engine).revoke_branch(
            org_id, key_id, revoked_by=f"test-owner:{org_id}", reason="ws2"
        )
        dispatch = _dispatch_spy(monkeypatch)
        result = await _call(app_, raw_key, "rai_health", {})
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_denied"
        dispatch.assert_not_awaited()

    async def test_ceiling_reduced_denies_before_dispatch(
        self, governed_app_with_key, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from responsibleai.db import OrgAuthorityCeilingRepository
        from responsibleai.governance import OrgAuthorityCeiling

        app_, raw_key, org_id, engine, _key_id = governed_app_with_key
        await OrgAuthorityCeilingRepository(engine).set(
            OrgAuthorityCeiling(org_id=org_id, allowed_action_types=["rai_scan"]),
        )
        dispatch = _dispatch_spy(monkeypatch)
        result = await _call(app_, raw_key, "rai_health", {})
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_denied"
        dispatch.assert_not_awaited()


class TestLiveApprovalExecuteInvalidation:
    async def test_expired_approval_never_dispatches(
        self, governance_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from sqlalchemy import update

        from responsibleai.dashboard.app import _db_engine
        from responsibleai.db.engine import governance_approvals

        org_id, _kid, admin_key = await seed_org_with_key(
            name="Approval Exp Co",
            slug=f"appr-exp-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        headers = {"Authorization": f"Bearer {admin_key}"}
        approval_id = await _seed_dispatchable_approval(org_id)
        await governance_client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers=headers,
        )
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        async with _db_engine.raw.begin() as conn:
            await conn.execute(
                update(governance_approvals)
                .where(governance_approvals.c.id == approval_id)
                .values(expires_at=past)
            )
        dispatch = _dispatch_spy(monkeypatch)
        response = await governance_client.post(
            f"/api/governance/approvals/{approval_id}/execute",
            headers=headers,
        )
        assert response.status_code == 409
        dispatch.assert_not_awaited()

    async def test_rejected_approval_never_dispatches(
        self, governance_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        org_id, _kid, admin_key = await seed_org_with_key(
            name="Approval Reject Co",
            slug=f"appr-rej-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        headers = {"Authorization": f"Bearer {admin_key}"}
        approval_id = await _seed_dispatchable_approval(org_id)
        await governance_client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "REJECTED"},
            headers=headers,
        )
        dispatch = _dispatch_spy(monkeypatch)
        response = await governance_client.post(
            f"/api/governance/approvals/{approval_id}/execute",
            headers=headers,
        )
        assert response.status_code == 409
        dispatch.assert_not_awaited()

    async def test_consumed_approval_replay_never_dispatches(
        self, governance_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        org_id, _kid, admin_key = await seed_org_with_key(
            name="Approval Replay Co",
            slug=f"appr-replay-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        headers = {"Authorization": f"Bearer {admin_key}"}
        approval_id = await _seed_dispatchable_approval(org_id)
        await governance_client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers=headers,
        )
        dispatch = _dispatch_spy(monkeypatch)
        first = await governance_client.post(
            f"/api/governance/approvals/{approval_id}/execute",
            headers=headers,
        )
        assert first.status_code == 200
        assert dispatch.await_count == 1
        second = await governance_client.post(
            f"/api/governance/approvals/{approval_id}/execute",
            headers=headers,
        )
        assert second.status_code == 409
        assert dispatch.await_count == 1

    async def test_wrong_org_execute_never_dispatches(
        self, governance_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        org_id, _kid, admin_key = await seed_org_with_key(
            name="Approval Org A",
            slug=f"appr-a-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        _other_id, _kid, other_key = await seed_org_with_key(
            name="Approval Org B",
            slug=f"appr-b-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        approval_id = await _seed_dispatchable_approval(org_id)
        await governance_client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        dispatch = _dispatch_spy(monkeypatch)
        response = await governance_client.post(
            f"/api/governance/approvals/{approval_id}/execute",
            headers={"Authorization": f"Bearer {other_key}"},
        )
        assert response.status_code in {403, 404, 409}
        dispatch.assert_not_awaited()

    async def test_tampered_action_digest_never_dispatches(
        self, governance_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from sqlalchemy import update

        from responsibleai.dashboard.app import _db_engine
        from responsibleai.db.engine import governance_approvals

        org_id, _kid, admin_key = await seed_org_with_key(
            name="Approval Tamper Co",
            slug=f"appr-tamper-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        headers = {"Authorization": f"Bearer {admin_key}"}
        approval_id = await _seed_dispatchable_approval(org_id, arguments={"probe": "original"})
        await governance_client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers=headers,
        )
        async with _db_engine.raw.begin() as conn:
            await conn.execute(
                update(governance_approvals)
                .where(governance_approvals.c.id == approval_id)
                .values(action_digest="f" * 64)
            )
        dispatch = _dispatch_spy(monkeypatch)
        response = await governance_client.post(
            f"/api/governance/approvals/{approval_id}/execute",
            headers=headers,
        )
        assert response.status_code == 409
        dispatch.assert_not_awaited()

    async def test_intent_change_after_approval_never_dispatches(
        self, governance_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from sqlalchemy import update

        from responsibleai.dashboard.app import _db_engine
        from responsibleai.db.engine import governance_approvals

        org_id, _kid, admin_key = await seed_org_with_key(
            name="Approval Intent Co",
            slug=f"appr-intent-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        headers = {"Authorization": f"Bearer {admin_key}"}
        approval_id = await _seed_dispatchable_approval(org_id)
        await governance_client.post(
            f"/api/governance/approvals/{approval_id}/resolve",
            json={"outcome": "APPROVED"},
            headers=headers,
        )
        async with _db_engine.raw.begin() as conn:
            await conn.execute(
                update(governance_approvals)
                .where(governance_approvals.c.id == approval_id)
                .values(purpose="mutated-intent")
            )
        dispatch = _dispatch_spy(monkeypatch)
        response = await governance_client.post(
            f"/api/governance/approvals/{approval_id}/execute",
            headers=headers,
        )
        assert response.status_code == 409
        dispatch.assert_not_awaited()


class TestLiveMcpBindingSubstitution:
    async def test_cross_org_api_key_never_dispatches_other_tenant_tool(
        self, monkeypatch: pytest.MonkeyPatch, seed_runtime_authority,
    ) -> None:
        import responsibleai.db as db_module
        from responsibleai.dashboard.config import get_settings
        from responsibleai.db import OrgRepository, create_engine
        from responsibleai.mcp.server import _build_http_app
        from responsibleai.rbac.models import Plan

        settings_ = get_settings()
        monkeypatch.setattr(settings_, "mcp_governance_enabled", True)
        engine = create_engine(":memory:")
        await engine.init()
        monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
        org_repo = OrgRepository(engine)
        org_a = await org_repo.create_org("Org A", f"org-a-{uuid.uuid4().hex[:6]}", plan=Plan.ENTERPRISE)
        org_b = await org_repo.create_org("Org B", f"org-b-{uuid.uuid4().hex[:6]}", plan=Plan.ENTERPRISE)
        _ka, key_a = await org_repo.create_key(org_a.id, "key-a")
        _kb, key_b = await org_repo.create_key(org_b.id, "key-b")
        await seed_runtime_authority(
            engine,
            organization_id=org_a.id,
            principal_id=_ka.id,
            action_types=("rai_health",),
            targets=("rai_health",),
        )
        app_http = _build_http_app()
        dispatch = _dispatch_spy(monkeypatch)
        async with LifespanManager(app_http) as manager:
            result = await _call(manager.app, key_b, "rai_health", {})
        payload = json.loads(result.content[0].text)
        assert payload.get("error") == "governance_denied"
        dispatch.assert_not_awaited()
        await engine.close()

    async def test_argument_substitution_on_scan_denied(
        self, governed_app, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app_, raw_key, _org_id, _engine = governed_app
        dispatch = _dispatch_spy(monkeypatch)
        result = await _call(
            app_,
            raw_key,
            "rai_scan",
            {"text": "This is a bomb threat."},
        )
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_denied"
        dispatch.assert_not_awaited()
