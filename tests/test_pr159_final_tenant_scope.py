# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""PR #159 final tenant scope: webhook test, incidents, delete, and metrics."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.db.engine import create_engine
from responsibleai.db.incident_repository import IncidentRepository
from responsibleai.db.webhook_repository import WebhookConfigRepository
from responsibleai.incidents.logic import build_incident_record
from responsibleai.rbac.models import AuditEntry, Role
from responsibleai.webhooks.manager import WebhookManager
from responsibleai.webhooks.models import WebhookConfig, WebhookDelivery, WebhookEvent
from tests.org_http_fixtures import seed_org_with_key


def _incident(description: str) -> dict:
    return build_incident_record(description=description)


@pytest.mark.asyncio
async def test_incident_list_and_get_are_tenant_scoped() -> None:
    engine = create_engine(":memory:")
    await engine.init()
    repo = IncidentRepository(engine)
    row_a = await repo.create(_incident("a-secret"), org_id="org-a")
    row_b = await repo.create(_incident("b-secret"), org_id="org-b")
    row_null = await repo.create(_incident("null-secret"), org_id=None)

    listed_a = {row["incident_id"] for row in await repo.list(org_id="org-a")}
    listed_b = {row["incident_id"] for row in await repo.list(org_id="org-b")}
    listed_null = {row["incident_id"] for row in await repo.list(org_id=None)}
    assert listed_a == {row_a["incident_id"]}
    assert listed_b == {row_b["incident_id"]}
    assert listed_null == {row_null["incident_id"]}
    assert await repo.list(org_id="org-z") == []

    assert (await repo.get(row_a["incident_id"], org_id="org-a"))["description"] == "a-secret"
    assert await repo.get(row_b["incident_id"], org_id="org-a") is None
    assert await repo.get(row_a["incident_id"], org_id=None) is None
    assert await repo.get(row_b["incident_id"], org_id=None) is None
    assert (await repo.get(row_null["incident_id"], org_id=None))["description"] == "null-secret"
    assert await repo.get("missing", org_id="org-a") is None
    await engine.close()


@pytest.mark.asyncio
async def test_webhook_delete_requires_matching_scope() -> None:
    engine = create_engine(":memory:")
    await engine.init()
    repo = WebhookConfigRepository(engine)
    foreign = WebhookConfig(
        url="https://a.example/hook", events=[WebhookEvent.DRIFT_ALERT], org_id="org-a"
    )
    local = WebhookConfig(
        url="https://null.example/hook", events=[WebhookEvent.DRIFT_ALERT], org_id=None
    )
    await repo.create(foreign)
    await repo.create(local)
    assert await repo.delete(foreign.id, org_id=None) is False
    assert await repo.delete(foreign.id, org_id="org-b") is False
    assert len(await repo.list_all()) == 2
    assert await repo.delete(local.id, org_id=None) is True
    assert await repo.delete(foreign.id, org_id="org-a") is True
    assert await repo.list_all() == []
    await engine.close()


def test_webhook_get_for_scope_does_not_cross_tenants() -> None:
    manager = WebhookManager()
    foreign = manager.register(
        WebhookConfig(
            url="https://a.example/hook", events=[WebhookEvent.DRIFT_ALERT], org_id="org-a"
        )
    )
    local = manager.register(
        WebhookConfig(
            url="https://null.example/hook", events=[WebhookEvent.DRIFT_ALERT], org_id=None
        )
    )
    assert manager.get_for_scope(foreign.id, "org-a") is foreign
    assert manager.get_for_scope(foreign.id, "org-b") is None
    assert manager.get_for_scope(foreign.id, None) is None
    assert manager.get_for_scope(local.id, None) is local
    assert manager.get_for_scope("missing", None) is None
    assert manager.platform_webhook_count() == 2
    assert [item.id for item in manager.list_webhooks()] == [local.id]


@pytest.mark.asyncio
async def test_revoke_and_eval_reads_do_not_treat_none_as_global() -> None:
    from responsibleai.db.eval_repository import EvalRepository
    from responsibleai.db.org_repository import OrgRepository

    engine = create_engine(":memory:")
    await engine.init()
    orgs = OrgRepository(engine)
    org_a = await orgs.create_org("A", "a")
    key_a, _ = await orgs.create_key(org_a.id, "a-key")
    assert await orgs.revoke_key(key_a.id, org_id=None) is False
    assert await orgs.revoke_key(key_a.id, org_id="org-b") is False
    assert (await orgs.get_key(key_a.id)).revoked is False
    assert await orgs.revoke_key(key_a.id, org_id=org_a.id) is True

    evals = EvalRepository(engine)
    run_a = await evals.save_run("compare", "m", {"secret": "a"}, org_id="org-a")
    run_null = await evals.save_run("compare", "m", {"secret": "null"}, org_id=None)
    assert await evals.get_run(run_a, org_id=None) is None
    assert await evals.get_run(run_a, org_id="org-b") is None
    assert (await evals.get_run(run_a, org_id="org-a"))["payload"]["secret"] == "a"
    assert (await evals.get_run(run_null, org_id=None))["payload"]["secret"] == "null"
    assert await evals.delete_run(run_a, org_id=None) is False
    assert [row["id"] for row in await evals.list_runs(org_id=None)] == [run_null]
    await evals.set_baseline("m", "suite", "accuracy", 0.5, org_id="org-a")
    await evals.set_baseline("m", "suite", "accuracy", 0.1, org_id=None)
    assert await evals.get_baselines("m", org_id=None) == {"suite:accuracy": 0.1}
    assert await evals.get_baselines("m", org_id="org-a") == {"suite:accuracy": 0.5}
    assert await evals.delete_baselines("m", org_id=None) == 1
    assert await evals.get_baselines("m", org_id="org-a") == {"suite:accuracy": 0.5}
    await engine.close()


@pytest.mark.asyncio
async def test_audit_none_is_null_scope_and_platform_is_explicit() -> None:
    from responsibleai.db.audit_repository import AuditRepository

    engine = create_engine(":memory:")
    await engine.init()
    repo = AuditRepository(engine)
    await repo.write(AuditEntry(endpoint="/api/a", method="GET", org_id="org-a"))
    await repo.write(AuditEntry(endpoint="/api/null", method="GET", org_id=None))
    scoped = await repo.query(org_id=None, days=1)
    assert [row["endpoint"] for row in scoped] == ["/api/null"]
    assert await repo.count(days=1, org_id=None) == 1
    assert await repo.count(days=1, org_id="org-a") == 1
    platform = await repo.query_platform(days=1)
    assert {row["endpoint"] for row in platform} == {"/api/a", "/api/null"}
    assert await repo.count_platform(days=1) == 2
    await engine.close()


@pytest.fixture()
def _auth_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    limiter.reset()


@pytest.fixture()
async def client(_auth_on: None):
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as http:
            yield http


def _patch_delivery(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    called: list[str] = []

    async def _fake_deliver(self, cfg, event, data, delivery_id=None, start_attempt=0):
        del self, data, delivery_id, start_attempt
        called.append(cfg.url)
        return WebhookDelivery(
            webhook_id=cfg.id,
            event=event,
            payload={},
            org_id=cfg.org_id,
            success=True,
            status_code=204,
        )

    monkeypatch.setattr(WebhookManager, "_deliver", _fake_deliver)
    monkeypatch.setattr(
        "responsibleai.webhooks.manager.socket.getaddrinfo",
        lambda host, *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )
    monkeypatch.setattr(
        "responsibleai.data_governance.backup_defense.assert_restore_readiness_admitted",
        lambda: None,
    )
    return called


async def _admin(slug: str) -> tuple[str, dict[str, str]]:
    org_id, _key, raw = await seed_org_with_key(
        name=slug, slug=slug, key_name="admin", role=Role.ADMIN
    )
    return org_id, {"Authorization": f"Bearer {raw}"}


@pytest.mark.asyncio
async def test_webhook_test_route_matrix(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = _patch_delivery(monkeypatch)
    _org_a, headers_a = await _admin("scope-a")
    _org_b, headers_b = await _admin("scope-b")
    body = {
        "url": "https://hooks.example.com/a",
        "events": ["trust_score_changed"],
        "provider": "generic",
    }
    created_a = await client.post("/api/webhooks", json=body, headers=headers_a)
    created_b = await client.post(
        "/api/webhooks",
        json={**body, "url": "https://hooks.example.com/b", "org_id": _org_a},
        headers=headers_b,
    )
    assert created_a.status_code == 200
    assert created_b.status_code == 200
    id_a = created_a.json()["id"]
    id_b = created_b.json()["id"]

    own = await client.post(f"/api/webhooks/test/{id_a}", headers=headers_a)
    assert own.status_code == 200
    assert called == ["https://hooks.example.com/a"]
    cross = await client.post(
        f"/api/webhooks/test/{id_b}",
        headers={**headers_a, "X-Org-Id": _org_b},
    )
    assert cross.status_code == 404
    assert id_b not in cross.text
    assert _org_b not in cross.text
    assert "hooks.example.com/b" not in cross.text
    assert called == ["https://hooks.example.com/a"]
    missing = await client.post("/api/webhooks/test/missing", headers=headers_a)
    assert missing.status_code == 404

    from responsibleai.dashboard import app as app_module

    local = WebhookConfig(
        url="https://hooks.example.com/null",
        events=[WebhookEvent.TRUST_SCORE_CHANGED],
        org_id=None,
    )
    app_module._webhook_manager.register(local)
    settings.auth_enabled = False
    limiter.reset()
    null_own = await client.post(f"/api/webhooks/test/{local.id}")
    assert null_own.status_code == 200
    assert called[-1] == "https://hooks.example.com/null"
    before = list(called)
    denied_a = await client.post(f"/api/webhooks/test/{id_a}?org_id={_org_a}")
    denied_b = await client.post(f"/api/webhooks/test/{id_b}", headers={"X-Org-Id": _org_b})
    assert denied_a.status_code == 404
    assert denied_b.status_code == 404
    assert id_a not in denied_a.text
    assert "hooks.example.com/a" not in denied_a.text
    assert "hooks.example.com/b" not in denied_b.text
    assert called == before


@pytest.mark.asyncio
async def test_incident_route_matrix(client: AsyncClient) -> None:
    _org_a, headers_a = await _admin("inc-a")
    _org_b, headers_b = await _admin("inc-b")
    created_a = await client.post(
        "/api/incidents",
        json={"description": "alpha-only", "org_id": _org_b},
        headers=headers_a,
    )
    created_b = await client.post(
        "/api/incidents", json={"description": "beta-only"}, headers=headers_b
    )
    assert created_a.status_code == 201
    assert created_b.status_code == 201
    id_a = created_a.json()["incident_id"]
    id_b = created_b.json()["incident_id"]

    listed_a = await client.get(
        f"/api/incidents?org_id={_org_b}", headers={**headers_a, "X-Org-Id": _org_b}
    )
    assert listed_a.status_code == 404
    listed_a_own = await client.get("/api/incidents", headers=headers_a)
    assert [row["incident_id"] for row in listed_a_own.json()["incidents"]] == [id_a]
    foreign = await client.get(f"/api/incidents/{id_b}", headers=headers_a)
    assert foreign.status_code == 404
    assert "beta-only" not in foreign.text

    settings.auth_enabled = False
    limiter.reset()
    created_null = await client.post(
        "/api/incidents", json={"description": "null-only", "org_id": _org_a}
    )
    assert created_null.status_code == 201
    id_null = created_null.json()["incident_id"]
    listed_null = await client.get(f"/api/incidents?org_id={_org_a}")
    assert listed_null.status_code == 404
    listed_null_own = await client.get("/api/incidents")
    ids = [row["incident_id"] for row in listed_null_own.json()["incidents"]]
    assert id_null in ids
    assert id_a not in ids
    assert id_b not in ids
    assert (await client.get(f"/api/incidents/{id_null}")).status_code == 200
    assert (await client.get(f"/api/incidents/{id_a}")).status_code == 404
    assert (await client.get(f"/api/incidents/{id_b}")).status_code == 404


@pytest.mark.asyncio
async def test_health_is_counts_only_and_metrics_follow_caller(client: AsyncClient) -> None:
    _org_a, headers_a = await _admin("metric-a")
    health = await client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert isinstance(body["checks"]["webhooks_registered"], int)
    assert isinstance(body["checks"]["orgs"], int)
    text = health.text.lower()
    assert "https://" not in text
    assert "webhook_id" not in text
    from responsibleai.dashboard import app as app_module

    assert app_module._audit_repo is not None
    await app_module._audit_repo.write(
        AuditEntry(endpoint="/api/other-tenant", method="GET", org_id="org-other")
    )
    scoped_before = await app_module._audit_repo.count(30, org_id=_org_a)
    platform_before = await app_module._audit_repo.count_platform(30)
    metrics = await client.get("/api/metrics", headers=headers_a)
    assert metrics.status_code == 200
    # The request itself is audited after the handler reads the count.
    assert metrics.json()["audit_entries_30d"] == scoped_before
    assert scoped_before < platform_before
    assert "org-other" not in metrics.text
    assert "https://" not in metrics.text.lower()
