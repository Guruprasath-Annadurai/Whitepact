"""Tests for whitepact_* observability metrics (v3 authority-layer work,
Task #138): WhitePactRuntimeGateway.evaluate() decisions and approval
resolutions are now visible on the existing /metrics Prometheus
endpoint, distinct from the pre-v3 rai_* product metrics already there.
"""

from __future__ import annotations

import json

import httpx
import pytest
from asgi_lifespan import LifespanManager

from responsibleai.dashboard.prometheus import (
    get_metrics_output,
    observe_governance_approval,
    observe_governance_decision,
)
from responsibleai.db import OrgRepository, create_engine
from responsibleai.rbac.models import Plan, Role


class TestObserveGovernanceDecision:
    def test_decision_counter_and_latency_histogram_appear_in_output(self) -> None:
        observe_governance_decision("ALLOW", "MINIMAL", 0.001, org_id="metrics-test-org")
        body, content_type = get_metrics_output()
        text = body.decode()
        assert "text/plain" in content_type
        assert 'whitepact_decisions_total{decision="ALLOW",org_id="metrics-test-org",risk_tier="MINIMAL"}' in text
        assert "whitepact_evaluation_seconds" in text

    def test_unclassified_risk_tier_gets_a_real_label_not_empty(self) -> None:
        observe_governance_decision("DENY", None, 0.0005, org_id="metrics-test-org-2")
        body, _ = get_metrics_output()
        text = body.decode()
        assert (
            'whitepact_decisions_total{decision="DENY",org_id="metrics-test-org-2",risk_tier="UNCLASSIFIED"}'
            in text
        )

    def test_no_org_id_uses_unscoped_label(self) -> None:
        observe_governance_decision("ALLOW", "LOW", 0.001, org_id=None)
        body, _ = get_metrics_output()
        text = body.decode()
        assert 'org_id="unscoped"' in text


class TestObserveGovernanceApproval:
    def test_approval_outcome_counter_appears_in_output(self) -> None:
        observe_governance_approval("APPROVED", org_id="metrics-test-org-3")
        body, _ = get_metrics_output()
        text = body.decode()
        assert 'whitepact_approvals_total{org_id="metrics-test-org-3",outcome="APPROVED"}' in text


@pytest.fixture()
async def governed_app(monkeypatch: pytest.MonkeyPatch):
    import responsibleai.db as db_module
    from responsibleai.dashboard.config import get_settings
    from responsibleai.mcp.server import _build_http_app

    settings = get_settings()
    monkeypatch.setattr(settings, "mcp_governance_enabled", True)

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)

    org_repo = OrgRepository(engine)
    org = await org_repo.create_org("Metrics Co", "metrics-co", plan=Plan.ENTERPRISE)
    _key_rec, raw_key = await org_repo.create_key(org.id, "test-key", role=Role.ANALYST)

    app = _build_http_app()
    async with LifespanManager(app) as manager:
        yield manager.app, raw_key, org.id

    await engine.close()


class TestEndToEndDispatchEmitsMetrics:
    """Proves the wiring, not just the helper: a real governed MCP tool
    call increments whitepact_decisions_total in the same global
    prometheus_client REGISTRY the dashboard app's /metrics endpoint
    serves from (that endpoint itself, and its auth/routing, is already
    covered by test_dashboard_api.py -- this proves apply_governance()
    actually calls observe_governance_decision(), which no prior test
    did)."""

    async def test_governed_tool_call_increments_the_shared_registry(self, governed_app) -> None:
        app, raw_key, org_id = governed_app

        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        async with (
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
                headers={"Authorization": f"Bearer {raw_key}"},
            ) as http_client,
            streamable_http_client("/mcp", http_client=http_client) as (
                read_stream, write_stream, _get_session_id,
            ),
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool("rai_health", {})
                assert result.isError is not True
                json.loads(result.content[0].text)

        body, _ = get_metrics_output()
        text = body.decode()
        assert f'whitepact_decisions_total{{decision="ALLOW",org_id="{org_id}",risk_tier="MINIMAL"}}' in text
