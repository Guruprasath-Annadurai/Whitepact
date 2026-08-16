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
from responsibleai.governance import QUARANTINE_VIOLATION_THRESHOLD, WhitePactRuntimeGateway
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
            read_stream,
            write_stream,
            _get_session_id,
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
            app,
            raw_key,
            "rai_scan",
            {"text": "Contact me at alice@example.com about this."},
        )
        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        # rai_scan's own PII findings are computed on the ALREADY-REDACTED
        # text the governance layer handed it — the raw email never
        # reaches the tool at all.
        assert "alice@example.com" not in json.dumps(payload)

        records = await EvidenceRepository(engine).list_for_org(
            org_id, decision="ALLOW_WITH_REDACTION"
        )
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


class TestOrgAuthorityCeiling:
    """The org authority ceiling (v3 authority-layer work) enforced live
    on the real hosted MCP dispatch path — `mcp/governance_integration.py`
    fetches the org's ceiling and passes it as `parent_authority` on
    every call."""

    async def test_call_within_ceiling_proceeds_normally(self, governed_app) -> None:
        from responsibleai.db import OrgAuthorityCeilingRepository
        from responsibleai.governance import OrgAuthorityCeiling

        app, raw_key, org_id, engine = governed_app
        await OrgAuthorityCeilingRepository(engine).set(
            OrgAuthorityCeiling(org_id=org_id, max_value_usd=500_000),
        )
        result = await _call(app, raw_key, "rai_health", {})
        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        assert "error" not in payload

    async def test_call_exceeding_ceiling_value_denied(self, governed_app) -> None:
        """A call carrying a real dollar argument over the ceiling's
        max_value_usd is denied through the existing, action-aware
        VALUE_LIMIT_EXCEEDED path -- not left unenforced, and not
        mis-denied as an escalation the way `rai_health` (no dollar
        argument at all) would be if the ceiling's constraints weren't
        copied onto the per-call authority."""
        from responsibleai.db import OrgAuthorityCeilingRepository
        from responsibleai.governance import OrgAuthorityCeiling

        app, raw_key, org_id, engine = governed_app
        await OrgAuthorityCeilingRepository(engine).set(
            OrgAuthorityCeiling(org_id=org_id, max_value_usd=500_000),
        )
        result = await _call(app, raw_key, "rai_scan", {"text": "hello", "amount_usd": 999_999})
        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_denied"
        assert any(r.startswith("VALUE_LIMIT_EXCEEDED") for r in payload["reason_codes"])

    async def test_ceiling_restricted_action_type_denied(self, governed_app) -> None:
        """A ceiling that only allows a different tool denies rai_health
        before dispatch, as an escalation -- rai_health isn't in the
        ceiling's own allowlist, and every per-call authority requests
        exactly the tool being called."""
        from responsibleai.db import OrgAuthorityCeilingRepository
        from responsibleai.governance import OrgAuthorityCeiling

        app, raw_key, org_id, engine = governed_app
        await OrgAuthorityCeilingRepository(engine).set(
            OrgAuthorityCeiling(org_id=org_id, allowed_action_types=["rai_scan"]),
        )
        result = await _call(app, raw_key, "rai_health", {})
        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_denied"
        assert any(r.startswith("DELEGATION_AUTHORITY_ESCALATION") for r in payload["reason_codes"])

        records = await EvidenceRepository(engine).list_for_org(org_id, decision="DENY")
        assert any(r.action_type == "rai_health" for r in records)

    async def test_no_ceiling_configured_unaffected(self, governed_app) -> None:
        """No row for this org (the default, before anyone configures
        one) -- behavior is identical to before ceilings existed."""
        app, raw_key, _org_id, _engine = governed_app
        result = await _call(app, raw_key, "rai_health", {})
        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        assert "error" not in payload


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
        self,
        governed_app,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import httpx as httpx_module
        import respx

        app, raw_key, org_id, engine = governed_app

        with respx.mock(base_url="https://responsibleai-dashboard.onrender.com") as mock:
            mock.get("/api/trust-index/check").mock(
                return_value=httpx_module.Response(
                    200,
                    json={
                        "model": "sketchy-model",
                        "provider": "unknown-vendor",
                        "known": True,
                        "trust_score": {"overall": 5.0},
                        "certified": False,
                        "has_reported_incidents": True,
                    },
                )
            )
            result = await _call(
                app,
                raw_key,
                "rai_cost_estimate",
                {
                    "model": "sketchy-model",
                    "provider": "unknown-vendor",
                    "input_tokens": 100,
                    "output_tokens": 50,
                },
            )

        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_approval_required"
        assert "approval_id" in payload

        from responsibleai.db import ApprovalRepository

        pending = await ApprovalRepository(engine).list_pending(org_id)
        assert any(p.action_type == "rai_cost_estimate" for p in pending)


class TestRequireApprovalFiresWebhook:
    async def test_queued_approval_fires_a_registered_webhook(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """webhooks/manager.py's validate_webhook_url() (the SSRF guard)
        does a real socket.getaddrinfo() lookup before every delivery, not
        just at registration — fake it to a fixed public IP the same way
        test_webhooks.py's _fake_public_dns fixture does, so this test
        doesn't depend on hooks.example.com being real DNS."""

        def _fake_getaddrinfo(host, *args, **kwargs):
            return [(2, 1, 6, "", ("93.184.216.34", 0))]

        monkeypatch.setattr(
            "responsibleai.webhooks.manager.socket.getaddrinfo",
            _fake_getaddrinfo,
        )
        """The dashboard REST API's approval endpoint already fires
        WebhookEvent.APPROVAL_REQUESTED via ApprovalRepository.create()'s
        webhook_manager parameter; this proves the MCP dispatch path now
        does the same, using the WebhookManager _build_http_app()
        constructs when governance is enabled."""
        import httpx as httpx_module
        import respx

        import responsibleai.db as db_module
        import responsibleai.webhooks.manager as webhook_manager_module
        from responsibleai.dashboard.config import get_settings
        from responsibleai.mcp.server import _build_http_app
        from responsibleai.webhooks.models import WebhookConfig, WebhookEvent

        settings = get_settings()
        monkeypatch.setattr(settings, "mcp_governance_enabled", True)

        engine = create_engine(":memory:")
        await engine.init()
        monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)

        created_managers: list[webhook_manager_module.WebhookManager] = []
        _real_webhook_manager_cls = webhook_manager_module.WebhookManager

        class _CapturingWebhookManager(_real_webhook_manager_cls):  # type: ignore[misc]
            def __init__(self) -> None:
                super().__init__()
                created_managers.append(self)

        monkeypatch.setattr(webhook_manager_module, "WebhookManager", _CapturingWebhookManager)

        org_repo = OrgRepository(engine)
        org = await org_repo.create_org("Webhook Co", "webhook-co", plan=Plan.ENTERPRISE)
        _key_rec, raw_key = await org_repo.create_key(org.id, "test-key", role=Role.ANALYST)

        app = _build_http_app()
        assert len(created_managers) == 1
        webhook_manager = created_managers[0]

        webhook_manager.register(
            WebhookConfig(
                url="https://hooks.example.com/mcp-approvals",
                events=[WebhookEvent.APPROVAL_REQUESTED],
                org_id=org.id,
            )
        )

        async with LifespanManager(app) as manager:
            with respx.mock(assert_all_called=False) as mock:
                mock.get("https://responsibleai-dashboard.onrender.com/api/trust-index/check").mock(
                    return_value=httpx_module.Response(
                        200,
                        json={
                            "model": "sketchy-model",
                            "provider": "unknown-vendor",
                            "known": True,
                            "trust_score": {"overall": 5.0},
                            "certified": False,
                            "has_reported_incidents": True,
                        },
                    )
                )
                webhook_route = mock.post("https://hooks.example.com/mcp-approvals").mock(
                    return_value=httpx_module.Response(200)
                )
                result = await _call(
                    manager.app,
                    raw_key,
                    "rai_cost_estimate",
                    {
                        "model": "sketchy-model",
                        "provider": "unknown-vendor",
                        "input_tokens": 100,
                        "output_tokens": 50,
                    },
                )
                assert webhook_route.call_count >= 1

        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_approval_required"

        await engine.close()


class TestEvidenceWriteFailsClosed:
    async def test_evidence_persistence_failure_blocks_an_otherwise_allowed_call(
        self,
        governed_app,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An action that would have been ALLOW must not execute if its
        evidence record can't be persisted — no evidence, no execution,
        rather than silently letting a call through with no audit trail.
        Patches EvidenceRepository.record at the class level so it
        affects the instance _build_http_app() already constructed."""
        app, raw_key, _org_id, _engine = governed_app

        async def _raise(self, evidence):
            raise RuntimeError("simulated transient DB failure")

        monkeypatch.setattr(EvidenceRepository, "record", _raise)

        result = await _call(app, raw_key, "rai_health", {})
        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_evidence_unavailable"
        assert "status" not in payload  # rai_health's own real response never ran


class TestAuthoritySubsystemCrashFailsClosed:
    """Distinct invariant from TestEvidenceWriteFailsClosed above: this
    proves a crash *inside the decision engine itself*
    (`WhitePactRuntimeGateway.evaluate()`) — not a downstream persistence
    failure — also fails closed. `apply_governance()` has no
    try/except around `services.gateway.evaluate(...)`; an exception
    there propagates out of `apply_governance()` before evidence is
    written and before `authorize_execution()`/`InternalToolExecutor`
    is ever reached, so the tool structurally cannot have run. What
    this test locks in: the MCP server layer must not convert that
    propagated exception into a silent ALLOW — either it surfaces as an
    MCP-protocol error, or a non-2xx/error CallToolResult, but never a
    normal tool payload."""

    async def test_gateway_exception_never_executes_the_tool(
        self,
        governed_app,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def _raise(self, action, authority, policy=None, *, recent_violation_count=0):
            raise RuntimeError("simulated authority/policy subsystem crash")

        monkeypatch.setattr(WhitePactRuntimeGateway, "evaluate", _raise)

        app, raw_key, org_id, engine = governed_app
        try:
            result = await _call(app, raw_key, "rai_health", {})
        except Exception:  # noqa: BLE001 -- either failure mode proves fail-closed
            pass
        else:
            # The MCP SDK caught it server-side and returned a result --
            # that result must be an explicit error, never rai_health's
            # real payload (which has a "status" key).
            assert result.isError is True or "status" not in json.loads(result.content[0].text)

        # No evidence exists for this call at all (not even a DENY) --
        # confirms build_evidence_record()/evidence_repo.record() were
        # never reached, i.e. execution never got past evaluate().
        records = await EvidenceRepository(engine).list_for_org(org_id)
        assert not any(r.action_type == "rai_health" for r in records)
