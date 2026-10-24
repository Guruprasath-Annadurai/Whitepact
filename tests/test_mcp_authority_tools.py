# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Option B: four read-only authority tools -- authorization, isolation, schema, side effects.

The service is exercised directly for the role / tenant / validation matrix (fast, exhaustive)
and through a real MCP client for protocol conformance and advertisement.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import func, select

from responsibleai.db import (
    ApprovalRepository,
    EvidenceRepository,
    OrgRepository,
    PolicyRepository,
    create_engine,
)
from responsibleai.db.engine import (
    governance_approvals,
    governance_evidence,
    governance_execution_nonces,
    governance_policies,
    governance_policy_history,
    governance_policy_versions,
)
from responsibleai.enterprise.security.rate_limit import DurableIdentityRateLimiter
from responsibleai.governance.approval import ApprovalRequest
from responsibleai.governance.evidence import EvidenceRecord
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.mcp.authority_tools import (
    AUTHORITY_TOOL_DEFS,
    AUTHORITY_TOOL_NAMES,
    LIST_PENDING_APPROVALS,
    POLICY_STATUS,
    SIMULATE_POLICY,
    VERIFY_EVIDENCE,
    AuthorityReadService,
)
from responsibleai.rbac.models import OrgContext, Plan, Role
from tests.protected_component_tenant import (
    attach_component_controller,
    component_controller,
    provision_component_organization,
)

_ALL_ROLES = list(Role)


@pytest.fixture()
async def world(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Any:
    async with component_controller(tmp_path, monkeypatch, "wp_mcp_auth") as controller:
        engine = controller.engine
        a = await provision_component_organization(
            engine, name="Org A", slug="org-a", plan=Plan.ENTERPRISE
        )
        b = await provision_component_organization(
            engine, name="Org B", slug="org-b", plan=Plan.ENTERPRISE
        )

        class _Services:
            policy_repo = PolicyRepository(engine)
            approval_repo = ApprovalRepository(engine)
            evidence_repo = EvidenceRepository(engine)

        service = AuthorityReadService(_Services(), DurableIdentityRateLimiter(engine))  # type: ignore[arg-type]
        yield engine, service, a.id, b.id


def _ctx(org_id: str | None, role: Role, *, legacy: bool = False) -> OrgContext:
    return OrgContext(
        key_id="key-1", role=role, org_id=org_id, plan=Plan.ENTERPRISE, is_legacy=legacy
    )


async def _pending(engine: Any, org_id: str, n: int, *, target: str = "secret-target") -> None:
    repo = ApprovalRepository(engine)
    for i in range(n):
        await repo.create(
            ApprovalRequest(
                action_id=str(uuid.uuid4()),
                action_type="payments.send",
                target=target,
                reason_codes=["NEEDS_HUMAN"],
                requested_at=datetime.now(UTC) + timedelta(seconds=i),
                organization_id=org_id,
                risk_tier="HIGH",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )


# ---------------------------------------------------------------- schema / descriptors


def test_exactly_four_tools_all_read_only_closed_schema() -> None:
    assert AUTHORITY_TOOL_NAMES == {
        "whitepact_policy_status",
        "whitepact_simulate_policy",
        "whitepact_list_pending_approvals",
        "whitepact_verify_evidence",
    }
    assert {t.name for t in AUTHORITY_TOOL_DEFS} == set(AUTHORITY_TOOL_NAMES)
    for tool in AUTHORITY_TOOL_DEFS:
        ann = tool.annotations
        assert ann is not None
        assert (ann.readOnlyHint, ann.destructiveHint, ann.idempotentHint, ann.openWorldHint) == (
            True,
            False,
            True,
            False,
        )
        assert tool.inputSchema["additionalProperties"] is False
        assert len(tool.name) <= 64
        assert "_whitepact_purpose" not in tool.inputSchema["properties"]
    # No tool can carry an organization id: the tenant comes only from the credential.
    for tool in AUTHORITY_TOOL_DEFS:
        assert not {"org_id", "organization_id", "tenant"} & set(tool.inputSchema["properties"])


# ---------------------------------------------------------------- negative authorization


@pytest.mark.parametrize(
    ("tool", "args", "denied"),
    [
        (
            POLICY_STATUS,
            {},
            {Role.VIEWER, Role.AUDITOR, Role.APPROVER, Role.DEVELOPER, Role.BILLING_ADMIN},
        ),
        (
            SIMULATE_POLICY,
            {"action_type": "x", "target": "y"},
            {Role.VIEWER, Role.AUDITOR, Role.APPROVER, Role.DEVELOPER, Role.BILLING_ADMIN},
        ),
        (
            LIST_PENDING_APPROVALS,
            {},
            {Role.VIEWER, Role.AUDITOR, Role.ANALYST, Role.DEVELOPER, Role.BILLING_ADMIN},
        ),
        (VERIFY_EVIDENCE, {}, {Role.VIEWER, Role.APPROVER, Role.DEVELOPER, Role.BILLING_ADMIN}),
    ],
)
async def test_role_matrix_is_explicit_default_deny(world, tool, args, denied) -> None:
    _engine, service, org_a, _b = world
    for role in _ALL_ROLES:
        result = await service.call(tool, dict(args), _ctx(org_a, role))
        if role in denied:
            assert result["error"] == "role_not_permitted", (tool, role)
        else:
            assert "error" not in result, (tool, role, result)


@pytest.mark.parametrize("tool", sorted(AUTHORITY_TOOL_NAMES))
async def test_legacy_and_unscoped_credentials_are_refused(world, tool) -> None:
    _e, service, org_a, _b = world
    args = {"action_type": "x", "target": "y"} if tool == SIMULATE_POLICY else {}
    assert (await service.call(tool, args, _ctx(None, Role.OWNER)))["error"] == (
        "tenant_credential_required"
    )
    assert (await service.call(tool, args, _ctx(org_a, Role.OWNER, legacy=True)))["error"] == (
        "tenant_credential_required"
    )


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        (POLICY_STATUS, {"org_id": "other"}),
        (SIMULATE_POLICY, {"action_type": "x", "target": "y", "organization_id": "other"}),
        (LIST_PENDING_APPROVALS, {"org_id": "other"}),
        (VERIFY_EVIDENCE, {"tenant": "other"}),
        (SIMULATE_POLICY, {"action_type": "x"}),
        (SIMULATE_POLICY, {"action_type": "x y", "target": "y"}),
        (SIMULATE_POLICY, {"action_type": "x" * 129, "target": "y"}),
        (SIMULATE_POLICY, {"action_type": "x", "target": "y", "risk_tier": "SEVERE"}),
        (LIST_PENDING_APPROVALS, {"limit": 0}),
        (LIST_PENDING_APPROVALS, {"limit": 51}),
        (LIST_PENDING_APPROVALS, {"limit": True}),
        (LIST_PENDING_APPROVALS, {"limit": "5"}),
        (LIST_PENDING_APPROVALS, {"cursor": "-1"}),
        (LIST_PENDING_APPROVALS, {"cursor": "9999"}),
        (LIST_PENDING_APPROVALS, {"cursor": "abc"}),
        (VERIFY_EVIDENCE, {"expected_head_hash": "XYZ"}),
        (VERIFY_EVIDENCE, {"expected_head_hash": "A" * 64}),
    ],
)
async def test_invalid_or_tenant_override_arguments_are_rejected(world, tool, args) -> None:
    _e, service, org_a, _b = world
    result = await service.call(tool, args, _ctx(org_a, Role.OWNER))
    assert result["error"] == "invalid_arguments", (args, result)


async def test_unknown_tool_is_refused(world) -> None:
    _e, service, org_a, _b = world
    assert (await service.call("rai_health", {}, _ctx(org_a, Role.OWNER)))["error"] == (
        "unknown_tool"
    )


# ---------------------------------------------------------------- tenant isolation


async def test_policy_tools_see_only_the_callers_tenant(world) -> None:
    engine, service, org_a, org_b = world
    policy = PolicyRepository(engine)
    await policy.add_rule(
        org_a,
        PolicyRule("deny-pay", "NO_PAY", GovernanceDecision.DENY, action_types=frozenset({"pay"})),
    )
    await policy.add_rule(
        org_b,
        PolicyRule(
            "allow-pay", "OK_PAY", GovernanceDecision.ALLOW, action_types=frozenset({"pay"})
        ),
    )
    sim = {"action_type": "pay", "target": "t"}
    a = await service.call(SIMULATE_POLICY, sim, _ctx(org_a, Role.ANALYST))
    b = await service.call(SIMULATE_POLICY, sim, _ctx(org_b, Role.ANALYST))
    assert (a["policy_effect"], a["reason_code"]) == ("DENY", "NO_PAY")
    assert (b["policy_effect"], b["reason_code"]) == ("ALLOW", "OK_PAY")

    status = await service.call(POLICY_STATUS, {}, _ctx(org_a, Role.ANALYST))
    assert status["rule_count"] == 1 and status["rules_by_effect"] == {"DENY": 1}
    assert status["history_chain_valid"] is True
    flat = json.dumps(status)
    assert "deny-pay" not in flat and "NO_PAY" not in flat  # no rule bodies / ids


async def test_pending_approvals_are_tenant_scoped_minimal_and_paginated(world) -> None:
    engine, service, org_a, org_b = world
    await _pending(engine, org_a, 5)
    await _pending(engine, org_b, 2)
    ctx_a = _ctx(org_a, Role.APPROVER)

    first = await service.call(LIST_PENDING_APPROVALS, {"limit": 2}, ctx_a)
    assert first["returned"] == 2 and first["next_cursor"] == "2"
    second = await service.call(
        LIST_PENDING_APPROVALS, {"limit": 2, "cursor": first["next_cursor"]}, ctx_a
    )
    third = await service.call(
        LIST_PENDING_APPROVALS, {"limit": 2, "cursor": second["next_cursor"]}, ctx_a
    )
    ids = [x["approval_id"] for r in (first, second, third) for x in r["approvals"]]
    assert len(ids) == 5 == len(set(ids)) and third["next_cursor"] is None

    everything = json.dumps([first, second, third])
    assert "secret-target" not in everything  # targets are never disclosed
    for item in first["approvals"]:
        assert set(item) == {
            "approval_id",
            "action_type",
            "risk_tier",
            "reason_codes",
            "requested_at",
            "expires_at",
            "required_approvals",
        }
    b_ids = {
        x["approval_id"]
        for x in (await service.call(LIST_PENDING_APPROVALS, {}, _ctx(org_b, Role.APPROVER)))[
            "approvals"
        ]
    }
    assert len(b_ids) == 2 and not b_ids & set(ids)


async def test_evidence_verification_reports_scope_and_never_claims_anchoring(world) -> None:
    engine, service, org_a, org_b = world
    repo = EvidenceRepository(engine)
    for i in range(3):
        await repo.record(
            EvidenceRecord(
                action_id=f"a{i}",
                agent_id="agent",
                identity_id="identity",
                action_type="pay",
                target="t",
                argument_keys=[],
                authority_delegated_by=org_a,
                decision="ALLOW",
                reason_codes=[],
                evaluated_at=datetime.now(UTC),
                organization_id=org_a,
            )
        )
    ctx = _ctx(org_a, Role.AUDITOR)
    result = await service.call(VERIFY_EVIDENCE, {}, ctx)
    assert result["chain_status"] in {"VALID", "INCOMPLETE"}
    assert result["externally_anchored"] is False
    assert result["scope"] == "internal_chain_consistency"
    assert result["head_sequence"] == 3 and len(result["head_hash"]) == 64
    assert "payload" not in json.dumps(result)

    match = await service.call(VERIFY_EVIDENCE, {"expected_head_hash": result["head_hash"]}, ctx)
    mismatch = await service.call(VERIFY_EVIDENCE, {"expected_head_hash": "0" * 64}, ctx)
    assert match["matches_expected_head"] is True and mismatch["matches_expected_head"] is False

    other = await service.call(VERIFY_EVIDENCE, {}, _ctx(org_b, Role.AUDITOR))
    assert other["head_sequence"] == 0 and other["head_hash"] is None  # org A's chain is invisible


async def test_a_tampered_chain_is_reported_invalid(world) -> None:
    engine, service, org_a, _b = world
    repo = EvidenceRepository(engine)
    await repo.record(
        EvidenceRecord(
            action_id="a",
            agent_id="g",
            identity_id="i",
            action_type="pay",
            target="t",
            argument_keys=[],
            authority_delegated_by=org_a,
            decision="ALLOW",
            reason_codes=[],
            evaluated_at=datetime.now(UTC),
            organization_id=org_a,
        )
    )
    async with engine.raw.begin() as conn:
        await conn.execute(
            governance_evidence.update()
            .where(governance_evidence.c.org_id == org_a)
            .values(decision="DENY")
        )
    result = await service.call(VERIFY_EVIDENCE, {}, _ctx(org_a, Role.OWNER))
    assert result["chain_status"] == "INVALID"


# ---------------------------------------------------------------- simulation honesty


async def test_simulation_is_labelled_policy_only_and_not_an_authorization(world) -> None:
    _e, service, org_a, _b = world
    result = await service.call(
        SIMULATE_POLICY, {"action_type": "pay", "target": "t"}, _ctx(org_a, Role.ANALYST)
    )
    assert result["simulation"] == "policy_only"
    assert result["is_authorization"] is False
    assert result["execution_grant_issued"] is False and result["recorded"] is False
    assert result["policy_effect"] == "NO_MATCHING_RULE"
    assert "approval state and four-eyes requirements" in result["not_evaluated"]


async def test_simulation_matches_the_canonical_evaluator(world) -> None:
    from responsibleai.governance.models import ActionRequest, AgentContext, IdentityContext
    from responsibleai.governance.risk import RiskTier

    engine, service, org_a, _b = world
    policy_repo = PolicyRepository(engine)
    await policy_repo.add_rule(
        org_a,
        PolicyRule(
            "r1",
            "R1",
            GovernanceDecision.REQUIRE_APPROVAL,
            risk_tiers=frozenset({RiskTier.HIGH}),
            action_types=frozenset({"pay"}),
        ),
    )
    policy = await policy_repo.get_policy(org_a)
    for tier in ("LOW", "HIGH"):
        direct = policy.evaluate(
            ActionRequest(
                agent=AgentContext(
                    identity=IdentityContext(identity_id="x", kind="agent", org_id=org_a),
                    organization_id=org_a,
                ),
                action_type="pay",
                target="t",
            ),
            RiskTier(tier),
        )
        got = await service.call(
            SIMULATE_POLICY,
            {"action_type": "pay", "target": "t", "risk_tier": tier},
            _ctx(org_a, Role.OWNER),
        )
        assert got["policy_effect"] == (direct.rule.effect.value if direct else "NO_MATCHING_RULE")


# ---------------------------------------------------------------- rate limiting


async def test_rate_limit_is_per_org_and_tool_and_fails_closed(world) -> None:
    _e, service, org_a, org_b = world
    ctx = _ctx(org_a, Role.OWNER)
    for _ in range(6):
        assert "error" not in await service.call(VERIFY_EVIDENCE, {}, ctx)
    assert (await service.call(VERIFY_EVIDENCE, {}, ctx))["error"] == "rate_limited"
    # Another org, and another tool in the same org, have their own budgets.
    assert "error" not in await service.call(VERIFY_EVIDENCE, {}, _ctx(org_b, Role.OWNER))
    assert "error" not in await service.call(POLICY_STATUS, {}, ctx)

    class _Broken:
        async def check(self, *_a: Any, **_k: Any) -> None:
            raise RuntimeError("limiter storage down")

    broken = AuthorityReadService(service.services, _Broken())
    result = await broken.call(POLICY_STATUS, {}, ctx)
    assert result["error"] == "authority_read_unavailable"


async def test_storage_failure_does_not_leak_driver_detail(world) -> None:
    _e, service, org_a, _b = world

    class _Boom:
        async def get_policy(self, *_a: Any) -> Any:
            raise RuntimeError("SELECT secret_column FROM tenants -- password=hunter2")

    class _S:
        policy_repo = _Boom()

    result = await AuthorityReadService(_S(), service.limiter).call(  # type: ignore[arg-type]
        POLICY_STATUS, {}, _ctx(org_a, Role.OWNER)
    )
    assert result["error"] == "authority_read_unavailable"
    assert "hunter2" not in json.dumps(result) and "SELECT" not in json.dumps(result)


# ---------------------------------------------------------------- no side effects


async def _snapshot(engine: Any) -> dict[str, Any]:
    tables = (
        governance_approvals,
        governance_evidence,
        governance_execution_nonces,
        governance_policies,
        governance_policy_history,
        governance_policy_versions,
    )
    out: dict[str, Any] = {}
    async with engine.raw.connect() as conn:
        for table in tables:
            rows = (await conn.execute(select(table))).fetchall()
            out[table.name] = sorted(repr(tuple(r)) for r in rows)
        out["nonces"] = (
            await conn.execute(select(func.count()).select_from(governance_execution_nonces))
        ).scalar()
    return out


async def test_the_four_tools_change_no_authority_state(world) -> None:
    engine, service, org_a, _b = world
    await PolicyRepository(engine).add_rule(
        org_a, PolicyRule("r", "R", GovernanceDecision.DENY, action_types=frozenset({"pay"}))
    )
    await _pending(engine, org_a, 3)
    before = await _snapshot(engine)
    ctx = _ctx(org_a, Role.OWNER)
    calls = [
        (POLICY_STATUS, {}),
        (SIMULATE_POLICY, {"action_type": "pay", "target": "t"}),
        (LIST_PENDING_APPROVALS, {"limit": 10}),
        (VERIFY_EVIDENCE, {}),
    ]
    for name, args in calls:
        assert "error" not in await service.call(name, args, ctx)
    after = await _snapshot(engine)
    # The durable rate-limiter counter is the only thing allowed to move, and it is not
    # authority state.
    assert after == before
    assert after["nonces"] == 0  # no execution grant was ever issued


def test_module_references_no_state_changing_repository_method() -> None:
    """Static guard on the code (not the prose): the module may not even name a mutator."""
    import ast
    import inspect

    import responsibleai.mcp.authority_tools as module

    names: set[str] = set()
    for node in ast.walk(ast.parse(inspect.getsource(module))):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.ImportFrom | ast.Import):
            names.update(a.name.split(".")[-1] for a in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                names.update(node.module.split("."))
    forbidden = {
        "resolve",
        "consume",
        "add_rule",
        "remove_rule",
        "reorder_rules",
        "record",
        "create",
        "create_from_decision",
        "authorize_execution",
        "apply_governance",
        "WhitePactRuntimeGateway",
        "gateway",
        "InternalToolExecutor",
        "dispatch_tool",
        "ExecutionNonceRepository",
        "RevocationEpochRepository",
    }
    assert not names & forbidden, sorted(names & forbidden)


# ---------------------------------------------------------------- real MCP client


@pytest.fixture()
async def governed_app(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Any:
    import responsibleai.db as db_module
    from responsibleai.dashboard.config import get_settings
    from responsibleai.mcp.server import _build_http_app

    monkeypatch.setattr(get_settings(), "mcp_governance_enabled", True)
    async with component_controller(tmp_path, monkeypatch, "wp_mcp_govapp") as controller:
        engine = controller.engine
        monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
        orgs = OrgRepository(engine)
        org = await provision_component_organization(
            engine, name="Gov Co", slug="gov-co", plan=Plan.ENTERPRISE
        )
        _k, owner_key = await orgs.create_key(org.id, "owner", role=Role.OWNER)
        _k, viewer_key = await orgs.create_key(org.id, "viewer", role=Role.VIEWER)
        app = _build_http_app()
        async with LifespanManager(app) as manager:
            yield manager.app, owner_key, viewer_key, org.id, engine


@pytest.fixture()
async def ungoverned_app(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Any:
    import responsibleai.db as db_module
    from responsibleai.dashboard.config import get_settings
    from responsibleai.mcp.server import _build_http_app

    monkeypatch.setattr(get_settings(), "mcp_governance_enabled", False)
    async with component_controller(tmp_path, monkeypatch, "wp_mcp_plain") as controller:
        engine = controller.engine
        monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
        orgs = OrgRepository(engine)
        org = await provision_component_organization(
            engine, name="Plain Co", slug="plain-co", plan=Plan.ENTERPRISE
        )
        _k, key = await orgs.create_key(org.id, "owner", role=Role.OWNER)
        app = _build_http_app()
        async with LifespanManager(app) as manager:
            yield manager.app, key


def _client(app: Any, key: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {key}"},
    )


async def _session_do(app: Any, key: str, fn: Any) -> Any:
    async with (
        _client(app, key) as http,
        streamable_http_client("/mcp", http_client=http) as (r, w, _sid),
        ClientSession(r, w) as session,
    ):
        await session.initialize()
        return await fn(session)


async def test_tools_are_advertised_and_callable_over_real_mcp(governed_app) -> None:
    app, owner, _viewer, _org, _engine = governed_app
    tools = await _session_do(app, owner, lambda s: s.list_tools())
    by_name = {t.name: t for t in tools.tools}
    assert AUTHORITY_TOOL_NAMES <= set(by_name)
    assert len(by_name) == 30 + 4
    for name in AUTHORITY_TOOL_NAMES:
        assert by_name[name].annotations.readOnlyHint is True

    result = await _session_do(app, owner, lambda s: s.call_tool(POLICY_STATUS, {}))
    assert not result.isError
    assert result.structuredContent["rule_contents_disclosed"] is False


async def test_viewer_is_refused_over_real_mcp_and_attempt_is_metered(governed_app) -> None:
    app, _owner, viewer, org, engine = governed_app
    result = await _session_do(app, viewer, lambda s: s.call_tool(POLICY_STATUS, {}))
    assert result.structuredContent["error"] == "role_not_permitted"
    from responsibleai.db.engine import mcp_tool_calls

    async with engine.raw.connect() as conn:
        rows = (
            await conn.execute(
                select(mcp_tool_calls).where(mcp_tool_calls.c.tool_name == POLICY_STATUS)
            )
        ).fetchall()
    assert rows and all(r.org_id == org for r in rows)
    assert [int(r.allowed) for r in rows] == [0]


async def test_schema_violations_are_rejected_by_the_protocol_or_service(governed_app) -> None:
    app, owner, _v, _o, _e = governed_app
    result = await _session_do(
        app,
        owner,
        lambda s: s.call_tool(SIMULATE_POLICY, {"action_type": "x", "target": "y", "org_id": "z"}),
    )
    assert result.isError or result.structuredContent.get("error") == "invalid_arguments"


async def test_without_governance_the_tools_are_not_advertised_or_runnable(ungoverned_app) -> None:
    app, key = ungoverned_app
    tools = await _session_do(app, key, lambda s: s.list_tools())
    assert not AUTHORITY_TOOL_NAMES & {t.name for t in tools.tools}
    result = await _session_do(app, key, lambda s: s.call_tool(POLICY_STATUS, {}))
    assert result.isError or result.structuredContent.get("error") in {
        "authority_tools_unavailable",
        "governance_unavailable",
    }


# ---------------------------------------------------------------- database privileges (Postgres)


@pytest.fixture()
async def pg() -> Any:
    from tests.test_v1_customer_journey import _pg_url, _upgrade_head

    async for url in _pg_url("wp_authro"):
        await _upgrade_head(url)
        yield url


async def test_tools_run_as_a_role_that_can_only_select_authority_tables(
    pg: str, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The read path's database contract: SELECT on the authority tables, and nothing else that
    matters. Proven by connecting as such a role -- a write would raise ``permission denied``."""
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import DBAPIError

    admin = create_engine(pg)
    await admin.init(auto_create_tables=False)
    role = f"wp_authority_ro_{uuid.uuid4().hex[:8]}"
    password = uuid.uuid4().hex
    read_tables = (
        "governance_policies",
        "governance_policy_versions",
        "governance_policy_history",
        "governance_approvals",
        "governance_evidence",
        "governance_evidence_chain_heads",
    )
    try:
        async with attach_component_controller(admin, tmp_path, monkeypatch):
            org = (
                await provision_component_organization(
                    admin, name="RO Co", slug="ro-co", plan=Plan.ENTERPRISE
                )
            ).id
        await PolicyRepository(admin).add_rule(
            org, PolicyRule("r", "R", GovernanceDecision.DENY, action_types=frozenset({"pay"}))
        )
        await _pending(admin, org, 2)
        async with admin.raw.begin() as conn:
            await conn.execute(text(f"CREATE ROLE \"{role}\" LOGIN PASSWORD '{password}'"))
            await conn.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
            for table in read_tables:
                await conn.execute(text(f'GRANT SELECT ON "{table}" TO "{role}"'))
            # The shared abuse limiter is the one thing the read path may write.
            await conn.execute(
                text(f'GRANT SELECT, INSERT, UPDATE ON identity_rate_counters TO "{role}"')
            )

        ro_url = make_url(pg).set(username=role, password=password)
        ro = create_engine(ro_url.render_as_string(hide_password=False))
        await ro.init(auto_create_tables=False)
        try:

            class _Services:
                policy_repo = PolicyRepository(ro)
                approval_repo = ApprovalRepository(ro)
                evidence_repo = EvidenceRepository(ro)

            service = AuthorityReadService(_Services(), DurableIdentityRateLimiter(ro))  # type: ignore[arg-type]
            ctx = _ctx(org, Role.OWNER)
            assert (await service.call(POLICY_STATUS, {}, ctx))["rule_count"] == 1
            sim = await service.call(SIMULATE_POLICY, {"action_type": "pay", "target": "t"}, ctx)
            assert sim["policy_effect"] == "DENY"
            assert (await service.call(LIST_PENDING_APPROVALS, {}, ctx))["returned"] == 2
            assert (await service.call(VERIFY_EVIDENCE, {}, ctx))["chain_status"] in {
                "VALID",
                "INCOMPLETE",
            }

            # And the role really cannot write authority state, nor mint a grant.
            for statement in (
                "UPDATE governance_policies SET reason_code = 'X'",
                "DELETE FROM governance_approvals",
                "DELETE FROM governance_evidence",
                "INSERT INTO governance_execution_nonces (nonce) VALUES ('n')",
            ):
                with pytest.raises(DBAPIError, match="permission denied"):
                    async with ro.raw.begin() as conn:
                        await conn.execute(text(statement))
        finally:
            await ro.close()
    finally:
        async with admin.raw.begin() as conn:
            exists = (
                await conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role})
            ).scalar()
            if exists:
                await conn.execute(text(f'DROP OWNED BY "{role}"'))
                await conn.execute(text(f'DROP ROLE "{role}"'))
        await admin.close()
