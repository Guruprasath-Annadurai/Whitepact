# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Web-session contracts over canonical approval and evidence truth."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

import responsibleai.dashboard.app as app_module
from responsibleai.dashboard.signup_guard import SignupRateWindow
from responsibleai.dashboard.web_governance_contracts import argument_summary
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.approval import ApprovalStatus, build_approval_request
from responsibleai.governance.evidence import build_evidence_record
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.outcome import OutcomeStatus, build_outcome_record
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL
from responsibleai.runtime.gate import PRODUCTION_GATE_B_OPEN, phase7a_dispatcher_flag_from_env
from tests.test_v1_customer_journey import (
    PURPOSE,
    _apply_idv,
    _invite_and_accept_admin,
    _login,
    _onboard,
    _pg_url,
    _quorum_approve_and_execute,
    _register,
    _token_from_url,
    _upgrade_head,
    _verify_login,
)

OWNER_A = "contract.owner.a@example.com"
ADMIN_A = "contract.admin.a@example.com"
VIEWER_A = "contract.viewer.a@example.com"
OWNER_B = "contract.owner.b@example.com"


@pytest.fixture()
async def pg_url() -> AsyncIterator[str]:
    async for url in _pg_url("wp_web_cc"):
        yield url


@pytest.fixture()
async def journey_client(monkeypatch: pytest.MonkeyPatch, pg_url: str):
    await _upgrade_head(pg_url)
    monkeypatch.setattr(app_module.settings, "database_url", pg_url)
    monkeypatch.setattr(app_module.settings, "db_path", ":memory:")
    monkeypatch.setattr(app_module.settings, "auto_migrate", False)
    monkeypatch.setattr(app_module.settings, "web_auth_dev_tokens", True)
    monkeypatch.setattr(app_module.settings, "web_session_secure", False)
    monkeypatch.setattr(app_module.settings, "web_verification_delivery_url", None)
    monkeypatch.setattr(app_module.settings, "paddle_webhook_secret", "paddle-test-placeholder")
    monkeypatch.setattr(app_module.settings, "environment", "development")
    monkeypatch.setattr(app_module.limiter, "enabled", False)
    monkeypatch.setattr(
        app_module, "_signup_window", SignupRateWindow(max_per_window=1000, window_seconds=3600.0)
    )
    async with LifespanManager(app_module.app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            yield client


async def _onboard_owner(client: AsyncClient, email: str, org_name: str) -> dict:
    _, body = await _register(client, name=org_name, email=email)
    csrf = await _verify_login(client, email, _token_from_url(body["verification_url"]))
    sess = await _onboard(client, csrf, org_name)
    await _apply_idv(client, sess["user"]["id"], f"evt-{email}")
    return sess


async def _invite_role(
    client: AsyncClient, *, owner_email: str, member_email: str, name: str, role: str
) -> None:
    csrf = client.cookies["wp_csrf"]
    invite = await client.post(
        "/api/v1/web/invitations",
        headers={"X-WP-CSRF": csrf},
        json={"email": member_email, "role": role},
    )
    assert invite.status_code == 202, invite.text
    token = _token_from_url(invite.json()["invitation_url"])
    await client.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": csrf})
    _, body = await _register(client, name=name, email=member_email)
    member_csrf = await _verify_login(
        client, member_email, _token_from_url(body["verification_url"])
    )
    accepted = await client.post(
        "/api/v1/web/invitations/accept",
        headers={"X-WP-CSRF": member_csrf},
        json={"token": token},
    )
    assert accepted.status_code == 200, accepted.text
    await client.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": client.cookies["wp_csrf"]})
    await _login(client, owner_email)


async def _seed_pending_approval(
    org_id: str,
    *,
    requested_by: str,
    required_approvals: int = 2,
    arguments: dict | None = None,
    purpose: str | None = "review-payment",
) -> str:
    identity = IdentityContext(identity_id=requested_by, kind="api_key", org_id=org_id)
    agent = AgentContext(identity=identity, organization_id=org_id)
    action = ActionRequest(
        agent=agent,
        action_type="deployment",
        target="prod",
        arguments=arguments or {},
        purpose=purpose,
    )
    authority = AuthorityContext(
        delegated_by=org_id,
        granted_action_types=frozenset({"deployment"}),
        require_approval_for=frozenset({"deployment"}),
    )
    decision = WhitePactRuntimeGateway().evaluate(action, authority)
    assert decision.decision is GovernanceDecision.REQUIRE_APPROVAL
    approval = build_approval_request(action, decision)
    approval.required_approvals = required_approvals
    saved = await app_module._approval_repo.create(approval)
    return saved.approval_id


async def _seed_evidence(org_id: str, *, decision: str | None = None):
    identity = IdentityContext(identity_id="principal-web", kind="api_key", org_id=org_id)
    agent = AgentContext(identity=identity, organization_id=org_id, agent_id="agent-web")
    action = ActionRequest(
        agent=agent,
        action_type="mcp_tool_call",
        target="rai_health",
        arguments={"token": "synthetic-secret"},
        purpose="web-contract",
    )
    authority = AuthorityContext(
        delegated_by=identity.identity_id,
        granted_action_types=frozenset({"mcp_tool_call"}),
    )
    evaluated = WhitePactRuntimeGateway().evaluate(action, authority)
    record = build_evidence_record(
        action,
        agent,
        authority,
        evaluated,
        authentication_method="api_key",
        authority_version="authority-v1",
        consent_id="consent-1",
        consent_version="consent-v1",
        governance_epoch=1,
    )
    if decision is not None:
        record.decision = decision
    return await app_module._evidence_repo.record(record)


def test_argument_summary_redacts_values() -> None:
    summary = argument_summary({"secret": "must-not-leak", "amount": "12"})
    assert summary == {"argument_keys": ["amount", "secret"], "argument_count": 2}
    assert argument_summary(None) is None


def test_authority_invariants_unchanged() -> None:
    assert PRODUCTION_GATE_B_OPEN is False
    os.environ.pop("PHASE7A_DISPATCHER_ENABLED", None)
    os.environ.pop("WHITEPACT_PHASE7A_DISPATCHER_ENABLED", None)
    os.environ.pop("RAI_PHASE7A_DISPATCHER_ENABLED", None)
    assert phase7a_dispatcher_flag_from_env() is False


async def test_approval_detail_votes_tenant_roles_and_redaction(
    journey_client: AsyncClient,
) -> None:
    client = journey_client
    sess = await _onboard_owner(client, OWNER_A, "Contract Org A")
    org_a = sess["organization"]["id"]
    owner_id = sess["user"]["id"]
    await _invite_and_accept_admin(
        client, owner_email=OWNER_A, admin_email=ADMIN_A, admin_name="Contract Admin"
    )
    await _invite_role(
        client, owner_email=OWNER_A, member_email=VIEWER_A, name="Contract Viewer", role="VIEWER"
    )

    await client.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": client.cookies["wp_csrf"]})
    sess_b = await _onboard_owner(client, OWNER_B, "Contract Org B")
    org_b = sess_b["organization"]["id"]
    foreign_id = await _seed_pending_approval(org_b, requested_by="foreign-key")
    await client.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": client.cookies["wp_csrf"]})
    await _login(client, OWNER_A)

    approval_id = await _seed_pending_approval(
        org_a,
        requested_by="agent-key",
        arguments={"secret": "do-not-echo", "amount": "42"},
    )
    zero = await client.get(f"/api/v1/web/approvals/{approval_id}")
    assert zero.status_code == 200, zero.text
    body = zero.json()
    assert body["approval_id"] == approval_id
    assert body["organization_id"] == org_a
    assert body["status"] == ApprovalStatus.PENDING.value
    assert body["required_approvals"] == 2
    assert body["current_vote_count"] == 0
    assert body["votes"] == []
    assert body["purpose"] == "review-payment"
    assert body["argument_summary"] == {"argument_keys": ["amount", "secret"], "argument_count": 2}
    assert "do-not-echo" not in zero.text
    assert "arguments" not in body

    foreign = await client.get(f"/api/v1/web/approvals/{foreign_id}")
    assert foreign.status_code == 404
    missing = await client.get("/api/v1/web/approvals/does-not-exist")
    assert missing.status_code == 404

    csrf = client.cookies["wp_csrf"]
    first = await client.post(
        f"/api/v1/web/approvals/{approval_id}/resolve",
        headers={"X-WP-CSRF": csrf},
        json={"outcome": "APPROVED"},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "PENDING"
    one = (await client.get(f"/api/v1/web/approvals/{approval_id}")).json()
    assert one["current_vote_count"] == 1
    assert one["status"] == "PENDING"
    assert len(one["votes"]) == 1
    assert one["votes"][0]["outcome"] == "APPROVED"

    duplicate = await client.post(
        f"/api/v1/web/approvals/{approval_id}/resolve",
        headers={"X-WP-CSRF": csrf},
        json={"outcome": "APPROVED"},
    )
    assert duplicate.status_code == 409

    self_id = await _seed_pending_approval(
        org_a, requested_by=f"web:{owner_id}", required_approvals=1
    )
    self_vote = await client.post(
        f"/api/v1/web/approvals/{self_id}/resolve",
        headers={"X-WP-CSRF": csrf},
        json={"outcome": "APPROVED"},
    )
    assert self_vote.status_code == 403

    deny_id = await _seed_pending_approval(org_a, requested_by="other-agent")
    denied = await client.post(
        f"/api/v1/web/approvals/{deny_id}/resolve",
        headers={"X-WP-CSRF": csrf},
        json={"outcome": "DENIED"},
    )
    assert denied.status_code == 200
    assert denied.json()["status"] == "DENIED"
    deny_detail = (await client.get(f"/api/v1/web/approvals/{deny_id}")).json()
    assert deny_detail["status"] == "DENIED"
    assert deny_detail["denied_vote_count"] == 1
    deny_exec = await client.post(
        f"/api/v1/web/approvals/{deny_id}/execute",
        headers={"X-WP-CSRF": csrf},
        json={},
    )
    assert deny_exec.status_code == 409

    await client.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": csrf})
    admin_csrf = await _login(client, ADMIN_A)
    second = await client.post(
        f"/api/v1/web/approvals/{approval_id}/resolve",
        headers={"X-WP-CSRF": admin_csrf},
        json={"outcome": "APPROVED"},
    )
    assert second.status_code == 200
    assert second.json()["status"] == "APPROVED"
    full = (await client.get(f"/api/v1/web/approvals/{approval_id}")).json()
    assert full["current_vote_count"] == 2
    assert full["status"] == "APPROVED"
    assert len(full["votes"]) == 2

    await client.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": admin_csrf})
    viewer_csrf = await _login(client, VIEWER_A)
    viewer_get = await client.get(f"/api/v1/web/approvals/{approval_id}")
    assert viewer_get.status_code == 200
    viewer_exec = await client.post(
        f"/api/v1/web/approvals/{approval_id}/execute",
        headers={"X-WP-CSRF": viewer_csrf},
        json={},
    )
    assert viewer_exec.status_code == 403


async def test_evidence_list_detail_verify_attestation_tenant_isolation(
    journey_client: AsyncClient,
) -> None:
    client = journey_client
    sess_a = await _onboard_owner(client, OWNER_A, "Evidence Org A")
    org_a = sess_a["organization"]["id"]
    recorded_a = await _seed_evidence(org_a)
    await app_module._outcome_repo.record(
        build_outcome_record(
            recorded_a.evidence_id,
            recorded_a.action_id,
            OutcomeStatus.UNKNOWN,
            organization_id=org_a,
            result_summary="acknowledgement lost; reconciliation required",
        )
    )
    await client.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": client.cookies["wp_csrf"]})
    sess_b = await _onboard_owner(client, OWNER_B, "Evidence Org B")
    org_b = sess_b["organization"]["id"]
    recorded_b = await _seed_evidence(org_b, decision="DENY")

    listed_b = await client.get("/api/v1/web/evidence", params={"limit": 20})
    assert listed_b.status_code == 200
    ids_b = {item["evidence_id"] for item in listed_b.json()["evidence"]}
    assert recorded_b.evidence_id in ids_b
    assert recorded_a.evidence_id not in ids_b
    deny_filter = await client.get("/api/v1/web/evidence", params={"decision": "DENY"})
    assert {item["evidence_id"] for item in deny_filter.json()["evidence"]} == {
        recorded_b.evidence_id
    }

    cross = await client.get(f"/api/v1/web/evidence/{recorded_a.evidence_id}")
    assert cross.status_code == 404
    cross_att = await client.get(f"/api/v1/web/evidence/{recorded_a.evidence_id}/attestation")
    assert cross_att.status_code == 404

    own = await client.get(f"/api/v1/web/evidence/{recorded_b.evidence_id}")
    assert own.status_code == 200
    assert own.json()["evidence_id"] == recorded_b.evidence_id
    assert own.json()["organization_id"] == org_b
    assert "synthetic-secret" not in own.text

    verify_b = await client.get("/api/v1/web/evidence/verify")
    assert verify_b.status_code == 200
    assert verify_b.json()["status"] in {"VALID", "INCOMPLETE"}
    assert verify_b.json()["chain_intact"] is True
    assert verify_b.json()["cryptographically_signed"] is False

    dashboard = await client.get("/api/v1/web/dashboard/evidence")
    assert dashboard.status_code == 200
    assert dashboard.json()["source"] == "evidence_repository"

    await client.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": client.cookies["wp_csrf"]})
    await _login(client, OWNER_A)
    listed_a = await client.get("/api/v1/web/evidence")
    ids_a = {item["evidence_id"] for item in listed_a.json()["evidence"]}
    assert recorded_a.evidence_id in ids_a
    assert recorded_b.evidence_id not in ids_a
    detail_a = await client.get(f"/api/v1/web/evidence/{recorded_a.evidence_id}")
    assert detail_a.status_code == 200
    attestation = await client.get(f"/api/v1/web/evidence/{recorded_a.evidence_id}/attestation")
    assert attestation.status_code == 200
    att = attestation.json()
    assert att["evidence_id"] == recorded_a.evidence_id
    assert att["outcome_status"] == OutcomeStatus.UNKNOWN.value
    assert att["cryptographically_signed"] is False
    assert "Not cryptographically signed" in att["integrity_note"]
    assert att["reconciliation_status"] in {"RECONCILED", "MISSING_OUTCOME", "ACTION_MISMATCH"}


async def test_web_execute_normalized_known_unknown_and_no_retry(
    journey_client: AsyncClient, monkeypatch, seed_runtime_authority
) -> None:
    client = journey_client
    monkeypatch.setattr(app_module.settings, "auth_enabled", True)
    sess = await _onboard_owner(client, OWNER_A, "Execute Org")
    org_id = sess["organization"]["id"]
    created = await client.post(
        "/api/v1/web/api-keys",
        headers={"X-WP-CSRF": client.cookies["wp_csrf"]},
        json={
            "name": "contract-agent",
            "environment": "test",
            "scopes": ["governance:read", "governance:write", "evidence:read"],
        },
    )
    assert created.status_code == 201, created.text
    raw = created.json()["api_key"]
    await _invite_and_accept_admin(
        client, owner_email=OWNER_A, admin_email=ADMIN_A, admin_name="Execute Admin"
    )
    from responsibleai.db import PolicyRepository, create_engine
    from responsibleai.db.org_repository import OrgRepository

    engine = create_engine(app_module.settings.database_url)
    await engine.init(auto_create_tables=False)
    ctx = await OrgRepository(engine).authenticate(raw)
    assert ctx is not None
    await seed_runtime_authority(
        engine,
        organization_id=org_id,
        principal_id=ctx.key_id,
        action_types=(SYNTHETIC_COUNTER_TOOL,),
        targets=(SYNTHETIC_COUNTER_TOOL,),
        purpose=PURPOSE,
    )
    await PolicyRepository(engine).add_rule(
        org_id,
        PolicyRule(
            rule_id="require-test-counter",
            reason_code="TEST_COUNTER_REQUIRES_APPROVAL",
            effect=GovernanceDecision.REQUIRE_APPROVAL,
            action_types=frozenset({SYNTHETIC_COUNTER_TOOL}),
        ),
    )
    await engine.close()

    pending = await client.post(
        "/api/v1/governance/tools/call",
        headers={"Authorization": f"Bearer {raw}"},
        json={"name": SYNTHETIC_COUNTER_TOOL, "arguments": {}, "purpose": PURPOSE},
    )
    assert pending.status_code == 200, pending.text
    approval_id = pending.json()["approval_id"]
    payload = await _quorum_approve_and_execute(
        client, approval_id, owner_email=OWNER_A, admin_email=ADMIN_A
    )
    assert payload["execution_status"] == OutcomeStatus.SUCCEEDED.value
    assert payload["reconciliation_required"] is False
    assert payload["evidence_id"]
    assert payload["outcome_id"]
    assert "error" not in payload
    resolved = await client.get(f"/api/v1/web/approvals/{approval_id}")
    assert resolved.json()["execution_state"] == "CONSUMED"

    lost = await client.post(
        "/api/v1/governance/tools/call",
        headers={"Authorization": f"Bearer {raw}"},
        json={
            "name": SYNTHETIC_COUNTER_TOOL,
            "arguments": {"fail_after_effect": True},
            "purpose": PURPOSE,
        },
    )
    unknown_id = lost.json()["approval_id"]
    unknown = await _quorum_approve_and_execute(
        client, unknown_id, owner_email=OWNER_A, admin_email=ADMIN_A
    )
    assert unknown["execution_status"] == OutcomeStatus.UNKNOWN.value
    assert unknown["reconciliation_required"] is True
    assert unknown["evidence_id"]
    assert unknown["outcome_id"]
    assert "will not retry automatically" in unknown["message"]
    retry = await client.post(
        f"/api/v1/web/approvals/{unknown_id}/execute",
        headers={"X-WP-CSRF": client.cookies["wp_csrf"]},
        json={},
    )
    assert retry.status_code == 409
    attestation = await client.get(f"/api/v1/web/evidence/{unknown['evidence_id']}/attestation")
    assert attestation.status_code == 200
    assert attestation.json()["outcome_status"] == OutcomeStatus.UNKNOWN.value
    assert attestation.json()["reconciliation_status"] == "RECONCILED"
