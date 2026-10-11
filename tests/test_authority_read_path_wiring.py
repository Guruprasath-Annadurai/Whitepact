# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Production wiring of the read-only authority tools: separate least-privilege database identity.

Checks the engine selection policy, then runs the real hosted app on Postgres with the tools bound to
a role that holds only SELECT on the authority tables, and re-tests authentication, role permissions,
cross-tenant isolation, read-only semantics and rate limiting through the real MCP transport.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import text
from sqlalchemy.engine import make_url

from responsibleai.db import OrgRepository, PolicyRepository, create_engine
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.mcp.server import select_authority_read_backend
from responsibleai.rbac.models import Plan, Role
from tests.test_mcp_authority_tools import _pending

# ------------------------------------------------------------------ selection policy


def test_production_without_a_dedicated_url_offers_no_tools() -> None:
    marker = object()
    assert select_authority_read_backend(
        database_url=None, production=True, main_engine=marker, engine_factory=lambda _u: 1 / 0
    ) == (None, None, None)


def test_dedicated_url_always_gets_its_own_engine_even_in_production() -> None:
    main, own = object(), object()
    engine, backend, limiter = select_authority_read_backend(
        database_url="postgresql://ro@h/db",
        production=True,
        main_engine=main,
        engine_factory=lambda url: own if url == "postgresql://ro@h/db" else main,
    )
    assert engine is own and backend is not None and limiter is not None


async def test_development_fallback_reuses_the_main_engine_and_owns_nothing() -> None:
    main = create_engine(":memory:")
    engine, backend, limiter = select_authority_read_backend(
        database_url=None, production=False, main_engine=main, engine_factory=lambda _u: 1 / 0
    )
    assert engine is None and backend is not None and limiter is not None
    await main.close()


# ------------------------------------------------------------------ Postgres, real app


@pytest.fixture()
async def stack(monkeypatch: pytest.MonkeyPatch) -> Any:
    import responsibleai.db as db_module
    from responsibleai.dashboard.config import get_settings
    from tests.test_v1_customer_journey import _pg_url, _upgrade_head

    async for url in _pg_url("wp_authwire"):
        await _upgrade_head(url)
        admin = create_engine(url)
        await admin.init(auto_create_tables=False)
        role, password = f"wp_ar_{uuid.uuid4().hex[:8]}", uuid.uuid4().hex
        tables = (
            "governance_policies governance_policy_versions governance_policy_history "
            "governance_approvals governance_evidence governance_evidence_chain_heads"
        ).split()
        async with admin.raw.begin() as conn:
            await conn.execute(text(f"CREATE ROLE \"{role}\" LOGIN PASSWORD '{password}'"))
            await conn.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
            for table in tables:
                await conn.execute(text(f'GRANT SELECT ON "{table}" TO "{role}"'))
            await conn.execute(
                text(f'GRANT SELECT, INSERT, UPDATE ON identity_rate_counters TO "{role}"')
            )
        ro_url = make_url(url).set(username=role, password=password).render_as_string(False)

        orgs = OrgRepository(admin)
        a = await orgs.create_org("Wire A", "wire-a", plan=Plan.ENTERPRISE)
        b = await orgs.create_org("Wire B", "wire-b", plan=Plan.ENTERPRISE)
        _k, owner_a = await orgs.create_key(a.id, "owner-a", role=Role.OWNER)
        _k, viewer_a = await orgs.create_key(a.id, "viewer-a", role=Role.VIEWER)
        rec_b, owner_b = await orgs.create_key(b.id, "owner-b", role=Role.OWNER)
        await PolicyRepository(admin).add_rule(
            a.id,
            PolicyRule(
                "deny-a", "A_ONLY", GovernanceDecision.DENY, action_types=frozenset({"pay"})
            ),
        )
        await _pending(admin, a.id, 2)
        await _pending(admin, b.id, 3)

        settings = get_settings()
        monkeypatch.setattr(settings, "mcp_governance_enabled", True)
        monkeypatch.setattr(settings, "authority_read_database_url", ro_url)
        real_factory = db_module.create_engine
        monkeypatch.setattr(
            db_module,
            "create_engine",
            lambda u, rf=real_factory, ro=ro_url, ad=admin: rf(u) if u == ro else ad,
        )
        from responsibleai.mcp.server import _build_http_app

        app = _build_http_app()
        async with LifespanManager(app) as manager:
            yield {
                "app": manager.app,
                "admin": admin,
                "role": role,
                "keys": {"owner_a": owner_a, "viewer_a": viewer_a, "owner_b": owner_b},
                "org_a": a.id,
                "org_b": b.id,
            }
        async with admin.raw.begin() as conn:
            await conn.execute(text(f'DROP OWNED BY "{role}"'))
            await conn.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
        await admin.close()


def _http(app: Any, key: str | None) -> httpx.AsyncClient:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver", headers=headers
    )


async def _call(stack: dict, key: str, tool: str, args: dict | None = None) -> dict:
    async with (
        _http(stack["app"], key) as http,
        streamable_http_client("/mcp", http_client=http) as (r, w, _sid),
        ClientSession(r, w) as session,
    ):
        await session.initialize()
        result = await session.call_tool(tool, args or {})
        return result.structuredContent or {"isError": True}


async def test_tools_run_on_the_least_privilege_connection(stack) -> None:
    out = await _call(stack, stack["keys"]["owner_a"], "whitepact_policy_status")
    assert out["rule_count"] == 1
    async with stack["admin"].raw.connect() as conn:
        users = {
            r[0]
            for r in (await conn.execute(text("SELECT usename FROM pg_stat_activity"))).fetchall()
        }
    assert stack["role"] in users  # the read path really holds its own, restricted connection


async def test_authentication_is_required_and_a_bad_credential_runs_nothing(stack) -> None:
    for key in (None, "wp_live_not-a-real-key", stack["keys"]["owner_a"] + "x"):
        async with _http(stack["app"], key) as http:
            response = await http.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "whitepact_policy_status", "arguments": {}},
                },
                headers={"Accept": "application/json, text/event-stream"},
            )
        assert response.status_code == 401, (key, response.status_code)


async def test_role_matrix_over_the_real_transport(stack) -> None:
    refused = await _call(stack, stack["keys"]["viewer_a"], "whitepact_policy_status")
    assert refused["error"] == "role_not_permitted"
    assert "rule_count" in await _call(stack, stack["keys"]["owner_a"], "whitepact_policy_status")


async def test_cross_tenant_isolation_over_the_real_transport(stack) -> None:
    a = await _call(stack, stack["keys"]["owner_a"], "whitepact_list_pending_approvals")
    b = await _call(stack, stack["keys"]["owner_b"], "whitepact_list_pending_approvals")
    assert a["returned"] == 2 and b["returned"] == 3
    assert not {x["approval_id"] for x in a["approvals"]} & {
        x["approval_id"] for x in b["approvals"]
    }
    sim = {"action_type": "pay", "target": "t"}
    assert (await _call(stack, stack["keys"]["owner_a"], "whitepact_simulate_policy", sim))[
        "policy_effect"
    ] == "DENY"
    assert (await _call(stack, stack["keys"]["owner_b"], "whitepact_simulate_policy", sim))[
        "policy_effect"
    ] == "NO_MATCHING_RULE"
    # An organization id smuggled in arguments is refused, never honoured.
    smuggled = await _call(
        stack,
        stack["keys"]["owner_b"],
        "whitepact_list_pending_approvals",
        {"org_id": stack["org_a"]},
    )
    assert smuggled.get("error") == "invalid_arguments" or smuggled.get("isError")


async def test_read_only_semantics_and_rate_limit_over_the_real_transport(stack) -> None:
    async def counts() -> tuple[int, ...]:
        out = []
        async with stack["admin"].raw.connect() as conn:
            for t in (
                "governance_approvals",
                "governance_policies",
                "governance_evidence",
                "governance_execution_nonces",
            ):
                out.append((await conn.execute(text(f"SELECT count(*) FROM {t}"))).scalar() or 0)
        return tuple(out)

    before = await counts()
    key = stack["keys"]["owner_a"]
    for _ in range(6):
        assert "error" not in await _call(stack, key, "whitepact_verify_evidence")
    assert (await _call(stack, key, "whitepact_verify_evidence"))["error"] == "rate_limited"
    await _call(stack, key, "whitepact_list_pending_approvals")
    assert await counts() == before  # nothing written, no grant minted
