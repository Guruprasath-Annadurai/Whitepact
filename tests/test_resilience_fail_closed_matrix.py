"""Tests for Enterprise Neural Phase 14 (Resilience + Fail-Closed
Operations).

Per `docs/enterprise-neural/14_PHASE14_DESIGN.md`: `THREAT_MODEL.md`
already documents two deliberately asymmetric cases — evidence-write
failures fail *closed* (explicit try/except,
`tests/test_mcp_governance_dispatch.py::TestEvidenceWriteFailsClosed`);
Trust Index lookups fail *open* (by design). A third case,
`WhitePactRuntimeGateway.evaluate()` crashing, is already proven to
fail closed by simple exception propagation
(`TestAuthoritySubsystemCrashFailsClosed` in that same file) — no
try/except wraps it; an exception structurally prevents evidence being
written or the executor being reached at all.

`apply_governance()` calls six more repository dependencies before
`evaluate()` — `ceiling_repo`, `policy_repo`, `delegation_repo`,
`workflow_rule_repo`, `autonomy_budget_repo`, `intent_repo` — none
individually wrapped in a try/except either, relying on the identical
propagation mechanism. This file generalizes
`TestAuthoritySubsystemCrashFailsClosed`'s exact pattern across all
six, so the matrix is regression-tested dependency-by-dependency
rather than assumed to transfer from the one dependency
(`gateway.evaluate()`) that already had a test.
"""

from __future__ import annotations

import json

import pytest
from asgi_lifespan import LifespanManager

from responsibleai.db import (
    DelegationRepository,
    EvidenceRepository,
    IntentContractRepository,
    OrgAuthorityCeilingRepository,
    OrgAutonomyBudgetRepository,
    OrgRepository,
    PolicyRepository,
    WorkflowRuleRepository,
    create_engine,
)
from responsibleai.rbac.models import Plan, Role


@pytest.fixture()
async def governed_app(monkeypatch: pytest.MonkeyPatch):
    """Identical to `test_mcp_governance_dispatch.py`'s own fixture of
    the same name -- duplicated, not imported, so this phase's
    contribution stays a single, independently deletable file (see
    every prior phase's own "Rollback procedure" convention)."""
    import responsibleai.db as db_module
    from responsibleai.dashboard.config import get_settings
    from responsibleai.mcp.server import _build_http_app

    settings = get_settings()
    monkeypatch.setattr(settings, "mcp_governance_enabled", True)

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)

    org_repo = OrgRepository(engine)
    org = await org_repo.create_org("Governed Co", "governed-co", plan=Plan.ENTERPRISE)
    _key_rec, raw_key = await org_repo.create_key(org.id, "test-key", role=Role.ANALYST)

    app = _build_http_app()
    async with LifespanManager(app) as manager:
        yield manager.app, raw_key, org.id, engine

    await engine.close()


async def _call(app, raw_key: str, tool_name: str, arguments: dict):
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            headers={"Authorization": f"Bearer {raw_key}"},
        ) as http_client,
        streamable_http_client("/mcp", http_client=http_client) as (
            read_stream,
            write_stream,
            _get_session_id,
        ),
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments)


def _raise(*_args, **_kwargs):
    raise RuntimeError("simulated dependency crash")


class TestPreEvaluateDependencyCrashesFailClosed:
    """Generalizes TestAuthoritySubsystemCrashFailsClosed
    (test_mcp_governance_dispatch.py) across every repository
    dependency apply_governance() calls before gateway.evaluate() --
    same invariant, same double-check (no real payload, no fabricated
    evidence), proven independently for each rather than assumed to
    transfer from the one dependency already covered."""

    @pytest.mark.parametrize(
        ("repo_class", "method_name"),
        [
            (OrgAuthorityCeilingRepository, "get"),
            (PolicyRepository, "get_policy"),
            (DelegationRepository, "get_latest_delegation"),
            (WorkflowRuleRepository, "get_rules"),
            (OrgAutonomyBudgetRepository, "get"),
            (IntentContractRepository, "get_active_for_agent"),
        ],
    )
    async def test_dependency_crash_never_executes_the_tool(
        self,
        governed_app,
        monkeypatch: pytest.MonkeyPatch,
        repo_class: type,
        method_name: str,
    ) -> None:
        monkeypatch.setattr(repo_class, method_name, _raise)

        app, raw_key, org_id, engine = governed_app
        try:
            result = await _call(app, raw_key, "rai_health", {})
        except Exception:  # noqa: BLE001 -- either failure mode proves fail-closed
            pass
        else:
            assert result.isError is True or "status" not in json.loads(result.content[0].text)

        records = await EvidenceRepository(engine).list_for_org(org_id)
        assert not any(r.action_type == "rai_health" for r in records)
