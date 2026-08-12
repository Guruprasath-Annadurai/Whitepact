"""Integration tests for the MCP dispatch-path governance wiring
(mcp/governance_integration.py + mcp/server.py's `_call_tool`) — closes
the gap where `dispatch_tool()` never routed through
`WhitePactRuntimeGateway`, even though the gateway itself, evidence
persistence, and the approval workflow all already existed as a
separate, opt-in REST API.

Real MCP client against the real Starlette ASGI app in-process, same
pattern as test_mcp_http_transport.py — proving actual protocol
behavior, not just `apply_governance()` in isolation (that's covered by
the governance-core unit tests).
"""

from __future__ import annotations

import json

import httpx
import pytest
from asgi_lifespan import LifespanManager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from responsibleai.db import EvidenceRepository, OrgRepository, create_engine
from responsibleai.governance import QUARANTINE_VIOLATION_THRESHOLD
from responsibleai.rbac.models import Plan, Role


@pytest.fixture()
async def governed_app(monkeypatch: pytest.MonkeyPatch):
    """Same DB-engine-substitution trick as test_mcp_http_transport.py's
    `seeded_app`, plus forcing `mcp_governance_enabled=True` on the
    shared Settings singleton before building the app — the feature is
    opt-in (default False), so every test in this file explicitly
    proves what changes *when it's turned on*, not the default state."""
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


@pytest.fixture()
async def ungoverned_app(monkeypatch: pytest.MonkeyPatch):
    """Same setup, but mcp_governance_enabled left at its False default
    — proves the feature genuinely changes nothing when off."""
    import responsibleai.db as db_module
    from responsibleai.mcp.server import _build_http_app

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)

    org_repo = OrgRepository(engine)
    org = await org_repo.create_org("Ungoverned Co", "ungoverned-co", plan=Plan.ENTERPRISE)
    _key_rec, raw_key = await org_repo.create_key(org.id, "test-key", role=Role.ANALYST)

    app = _build_http_app()
    async with LifespanManager(app) as manager:
        yield manager.app, raw_key

    await engine.close()


def _client(app, raw_key: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {raw_key}"},
    )


async def _call(app, raw_key: str, tool_name: str, arguments: dict):
    async with (
        _client(app, raw_key) as http_client,
        streamable_http_client("/mcp", http_client=http_client) as (
            read_stream, write_stream, _get_session_id,
        ),
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments)


class TestGovernanceDisabledByDefault:
    async def test_toxic_content_still_executes_when_disabled(self, ungoverned_app) -> None:
        """The exact same call that Section TestDenyBlocksExecution below
        proves gets blocked when governance is ON must still succeed
        normally when it's OFF (the default) — this is the concrete
        backward-compatibility proof, not just a docstring claim."""
        app, raw_key = ungoverned_app
        result = await _call(app, raw_key, "rai_scan", {"text": "This is a bomb threat."})
        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        assert payload["is_blocked"] is True  # rai_scan's own opinion, not a governance block
        assert "error" not in payload or payload.get("error") is None


class TestAllowPassesThrough:
    async def test_clean_call_executes_normally(self, governed_app) -> None:
        app, raw_key, _org_id, _engine = governed_app
        result = await _call(app, raw_key, "rai_health", {})
        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        assert "error" not in payload

    async def test_allow_writes_evidence(self, governed_app) -> None:
        app, raw_key, org_id, engine = governed_app
        await _call(app, raw_key, "rai_health", {})
        records = await EvidenceRepository(engine).list_for_org(org_id, decision="ALLOW")
        assert any(r.action_type == "rai_health" for r in records)


class TestPiiRedactionBeforeDispatch:
    async def test_pii_text_is_redacted_before_the_tool_sees_it(self, governed_app) -> None:
        app, raw_key, org_id, engine = governed_app
        result = await _call(
            app, raw_key, "rai_scan", {"text": "Contact me at alice@example.com about this."},
        )
        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        # rai_scan's own PII findings are computed on the ALREADY-REDACTED
        # text the governance layer handed it — the raw email never
        # reaches the tool at all.
        assert "alice@example.com" not in json.dumps(payload)

        records = await EvidenceRepository(engine).list_for_org(org_id, decision="ALLOW_WITH_REDACTION")
        assert any(r.action_type == "rai_scan" for r in records)


class TestDenyBlocksExecution:
    async def test_toxic_content_never_reaches_the_tool(self, governed_app) -> None:
        app, raw_key, org_id, engine = governed_app
        result = await _call(app, raw_key, "rai_scan", {"text": "This is a bomb threat."})
        assert result.isError is not True  # MCP-protocol-level success; the block is in the payload
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_denied"
        assert "reason_codes" in payload

        records = await EvidenceRepository(engine).list_for_org(org_id, decision="DENY")
        assert any(r.action_type == "rai_scan" for r in records)


class TestQuarantineAfterRepeatedViolations:
    async def test_repeated_denials_eventually_quarantine(self, governed_app) -> None:
        app, raw_key, _org_id, _engine = governed_app
        last_payload = None
        for _ in range(QUARANTINE_VIOLATION_THRESHOLD + 1):
            result = await _call(app, raw_key, "rai_scan", {"text": "This is a bomb threat."})
            last_payload = json.loads(result.content[0].text)
        assert last_payload["error"] == "governance_quarantined"


class TestRequireApprovalQueuesNotExecutes:
    async def test_low_trust_model_queues_approval_instead_of_executing(
        self, governed_app, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import httpx as httpx_module
        import respx

        app, raw_key, org_id, engine = governed_app

        with respx.mock(base_url="https://responsibleai-dashboard.onrender.com") as mock:
            mock.get("/api/trust-index/check").mock(
                return_value=httpx_module.Response(200, json={
                    "model": "sketchy-model", "provider": "unknown-vendor", "known": True,
                    "trust_score": {"overall": 5.0}, "certified": False, "has_reported_incidents": True,
                })
            )
            result = await _call(app, raw_key, "rai_cost_estimate", {
                "model": "sketchy-model", "provider": "unknown-vendor",
                "input_tokens": 100, "output_tokens": 50,
            })

        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_approval_required"
        assert "approval_id" in payload

        from responsibleai.db import ApprovalRepository

        pending = await ApprovalRepository(engine).list_pending(org_id)
        assert any(p.action_type == "rai_cost_estimate" for p in pending)
