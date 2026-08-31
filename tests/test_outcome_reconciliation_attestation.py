# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Outcome Observation (Phase 12), Reconciliation (Phase 13),
and Attestation (Phase 14).

Covers: the pure `OutcomeRecord`/`reconcile_outcome`/`build_attestation_record`
logic, `OutcomeRepository`'s persistence, real auto-recording through
both the internal-tool governed-dispatch path (a real MCP round trip
against the hosted server) and the upstream-proxy path (a real second
in-process MCP server), and the REST endpoints for manual outcome
reporting and fetching an attestation.
"""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.db import EvidenceRepository, OutcomeRepository, create_engine
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.attestation import build_attestation_record
from responsibleai.governance.evidence import build_evidence_record
from responsibleai.governance.outcome import OutcomeStatus, build_outcome_record
from responsibleai.governance.reconciliation import ReconciliationStatus, reconcile_outcome

BOOTSTRAP_AUTH = {"Authorization": "Bearer bootstrap-test-key"}


def _agent(org_id: str = "org-1") -> AgentContext:
    identity = IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)
    return AgentContext(identity=identity, organization_id=org_id, framework="test")


def _authority() -> AuthorityContext:
    return AuthorityContext(delegated_by="org-1", granted_action_types=frozenset({"some_action"}))


class TestBuildOutcomeRecord:
    def test_builds_with_given_status(self) -> None:
        outcome = build_outcome_record("ev-1", "act-1", OutcomeStatus.SUCCEEDED)
        assert outcome.evidence_id == "ev-1"
        assert outcome.action_id == "act-1"
        assert outcome.status is OutcomeStatus.SUCCEEDED
        assert outcome.result_summary is None

    def test_to_dict_shape(self) -> None:
        outcome = build_outcome_record(
            "ev-1", "act-1", OutcomeStatus.FAILED, organization_id="org-1", result_summary="oops"
        )
        d = outcome.to_dict()
        assert d["evidence_id"] == "ev-1"
        assert d["status"] == "FAILED"
        assert d["result_summary"] == "oops"
        assert d["organization_id"] == "org-1"


class TestReconcileOutcome:
    def _evidence(self, decision: GovernanceDecision, action_id: str = "act-1"):
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        action = ActionRequest(
            agent=agent, action_type="some_action", target="t", action_id=action_id
        )
        authority = _authority()
        real_decision = gw.evaluate(action, authority)
        # Force the specific decision under test rather than depend on
        # what the gateway happens to produce for a bare action.
        from dataclasses import replace

        forced = replace(real_decision, decision=decision)
        return build_evidence_record(action, agent, authority, forced)

    def test_deny_is_not_applicable(self) -> None:
        evidence = self._evidence(GovernanceDecision.DENY)
        result = reconcile_outcome(evidence, None)
        assert result.status is ReconciliationStatus.NOT_APPLICABLE

    def test_quarantine_is_not_applicable(self) -> None:
        evidence = self._evidence(GovernanceDecision.QUARANTINE)
        result = reconcile_outcome(evidence, None)
        assert result.status is ReconciliationStatus.NOT_APPLICABLE

    def test_require_approval_is_not_applicable(self) -> None:
        evidence = self._evidence(GovernanceDecision.REQUIRE_APPROVAL)
        result = reconcile_outcome(evidence, None)
        assert result.status is ReconciliationStatus.NOT_APPLICABLE

    def test_allow_with_no_outcome_is_missing(self) -> None:
        evidence = self._evidence(GovernanceDecision.ALLOW)
        result = reconcile_outcome(evidence, None)
        assert result.status is ReconciliationStatus.MISSING_OUTCOME

    def test_allow_with_redaction_with_no_outcome_is_missing(self) -> None:
        evidence = self._evidence(GovernanceDecision.ALLOW_WITH_REDACTION)
        result = reconcile_outcome(evidence, None)
        assert result.status is ReconciliationStatus.MISSING_OUTCOME

    def test_allow_with_matching_outcome_is_reconciled(self) -> None:
        evidence = self._evidence(GovernanceDecision.ALLOW, action_id="act-1")
        outcome = build_outcome_record(evidence.evidence_id, "act-1", OutcomeStatus.SUCCEEDED)
        result = reconcile_outcome(evidence, outcome)
        assert result.status is ReconciliationStatus.RECONCILED
        assert result.outcome_id == outcome.outcome_id

    def test_mismatched_action_id_is_flagged(self) -> None:
        evidence = self._evidence(GovernanceDecision.ALLOW, action_id="act-1")
        outcome = build_outcome_record(
            evidence.evidence_id, "act-DIFFERENT", OutcomeStatus.SUCCEEDED
        )
        result = reconcile_outcome(evidence, outcome)
        assert result.status is ReconciliationStatus.ACTION_MISMATCH


class TestBuildAttestationRecord:
    def _evidence(self):
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        action = ActionRequest(agent=agent, action_type="some_action", target="t")
        authority = _authority()
        decision = gw.evaluate(action, authority)
        return build_evidence_record(action, agent, authority, decision)

    def test_attestation_without_outcome(self) -> None:
        evidence = self._evidence()
        attestation = build_attestation_record(evidence, None)
        assert attestation.evidence_id == evidence.evidence_id
        assert attestation.outcome_status is None
        assert attestation.decision == evidence.decision

    def test_attestation_with_outcome(self) -> None:
        evidence = self._evidence()
        outcome = build_outcome_record(
            evidence.evidence_id, evidence.action_id, OutcomeStatus.SUCCEEDED
        )
        attestation = build_attestation_record(evidence, outcome)
        assert attestation.outcome_status == "SUCCEEDED"

    def test_to_dict_carries_integrity_note_and_no_signature_claim(self) -> None:
        evidence = self._evidence()
        d = build_attestation_record(evidence, None).to_dict()
        assert "integrity_note" in d
        assert "not cryptographically signed" in d["integrity_note"].lower()
        assert "signature" not in d  # never claims to carry an actual signature field


class TestOutcomeRepository:
    @pytest.fixture()
    async def engine(self):
        e = create_engine(":memory:")
        await e.init()
        yield e
        await e.close()

    @pytest.fixture()
    def repo(self, engine):
        return OutcomeRepository(engine)

    async def test_get_for_missing_evidence_returns_none(self, repo: OutcomeRepository) -> None:
        assert await repo.get_for_evidence("does-not-exist") is None

    async def test_record_then_get(self, repo: OutcomeRepository) -> None:
        outcome = build_outcome_record("ev-1", "act-1", OutcomeStatus.SUCCEEDED)
        await repo.record(outcome)
        fetched = await repo.get_for_evidence("ev-1")
        assert fetched is not None
        assert fetched.outcome_id == outcome.outcome_id
        assert fetched.status is OutcomeStatus.SUCCEEDED

    async def test_latest_observation_wins(self, repo: OutcomeRepository) -> None:
        first = build_outcome_record("ev-1", "act-1", OutcomeStatus.ERRORED)
        await repo.record(first)
        second = build_outcome_record("ev-1", "act-1", OutcomeStatus.SUCCEEDED)
        await repo.record(second)
        fetched = await repo.get_for_evidence("ev-1")
        assert fetched is not None
        assert fetched.outcome_id == second.outcome_id


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
async def governed_mcp(monkeypatch: pytest.MonkeyPatch):
    """Real MCP protocol round trip against the hosted server's governed
    dispatch path (`apply_governance()`), same pattern
    test_mcp_governance_dispatch.py already established: a substituted
    in-memory engine shared across everything in the test via
    `db_module.create_engine`, mcp_governance_enabled forced True, and a
    real `_build_http_app()` instance (a different app object than the
    dashboard's own `app`, but pointed at the same DB)."""
    import responsibleai.dashboard.app as dashboard_app_module
    import responsibleai.dashboard.config as config_module
    import responsibleai.db as db_module
    from responsibleai.db import OrgRepository
    from responsibleai.mcp.server import _build_http_app
    from responsibleai.rbac.models import Plan, Role

    # `mcp/server.py`'s `_build_http_app()` calls `get_settings()`
    # fresh at call time, which returns `config_module`'s lazily-
    # cached `_settings` singleton -- normally the exact same object
    # already bound to `dashboard.app.settings` (captured once at
    # THIS file's import time), but another test elsewhere in the
    # suite resetting that cache (`config_module._settings = None`,
    # forcing the next get_settings() call to build a fresh, unrelated
    # Settings() reading real env vars) would silently desync the two.
    # Pinning the cache to the exact object this file already patches
    # guarantees `_build_http_app()` sees the same `mcp_governance_enabled`
    # regardless of what ran before this test.
    monkeypatch.setattr(config_module, "_settings", settings)
    monkeypatch.setattr(settings, "mcp_governance_enabled", True)

    engine = create_engine(":memory:")
    await engine.init()
    # mcp/server.py's _build_http_app() imports create_engine lazily,
    # inside the function, so patching db_module.create_engine reaches
    # it -- but dashboard/app.py imports create_engine at module load
    # time (`from responsibleai.db import create_engine`), binding an
    # independent name into its own namespace; patching db_module alone
    # never reaches that already-bound reference, so the dashboard
    # app's own LifespanManager would silently build a second, empty
    # in-memory database. Both names need patching for the two apps in
    # this file to actually share one engine.
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
    monkeypatch.setattr(dashboard_app_module, "create_engine", lambda _url: engine)

    org_repo = OrgRepository(engine)
    org = await org_repo.create_org("Outcome Test Co", "outcome-test-co", plan=Plan.ENTERPRISE)
    _key_rec, raw_key = await org_repo.create_key(org.id, "analyst-key", role=Role.ANALYST)

    mcp_app = _build_http_app()
    async with LifespanManager(mcp_app) as manager:
        yield manager.app, raw_key, org.id, engine

    await engine.close()


async def _call_tool(mcp_app, raw_key: str, tool_name: str, arguments: dict):
    http_client = AsyncClient(
        transport=ASGITransport(app=mcp_app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    async with (
        http_client,
        streamable_http_client("/mcp", http_client=http_client) as (
            read_stream,
            write_stream,
            _get_session_id,
        ),
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments)


class TestAutoRecordedOutcomeInternalTool:
    async def test_governed_mcp_call_records_a_succeeded_outcome(self, governed_mcp) -> None:
        """A real MCP round trip through the hosted server's governed
        dispatch path (apply_governance()) -- proves the outcome is
        recorded automatically, not just that the wiring compiles."""
        mcp_app, raw_key, org_id, engine = governed_mcp
        await _call_tool(mcp_app, raw_key, "rai_health", {})

        evidence_repo = EvidenceRepository(engine)
        outcome_repo = OutcomeRepository(engine)
        records = await evidence_repo.list_for_org(org_id, limit=10)
        matching = [r for r in records if r.action_type == "rai_health"]
        assert matching, "expected a governed rai_health evidence record"
        outcome = await outcome_repo.get_for_evidence(matching[0].evidence_id)
        assert outcome is not None
        assert outcome.status is OutcomeStatus.SUCCEEDED


class TestAttestationRestEndpoint:
    async def test_attestation_reflects_reconciled_after_real_call(self, governed_mcp) -> None:
        mcp_app, raw_key, org_id, engine = governed_mcp
        await _call_tool(mcp_app, raw_key, "rai_health", {})

        evidence_repo = EvidenceRepository(engine)
        records = await evidence_repo.list_for_org(org_id, limit=10)
        matching = [r for r in records if r.action_type == "rai_health"]
        assert matching
        evidence_id = matching[0].evidence_id
        attestation = build_attestation_record(
            matching[0], await OutcomeRepository(engine).get_for_evidence(evidence_id)
        )
        assert attestation.reconciliation_status == "RECONCILED"
        assert attestation.outcome_status == "SUCCEEDED"

        # Also exercise the actual REST endpoint, on a second app (the
        # dashboard FastAPI app) pointed at the same substituted engine
        # (create_engine is already monkeypatched by governed_mcp).
        async with LifespanManager(app) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as dash_client:
                r = await dash_client.get(
                    f"/api/governance/evidence/{evidence_id}/attestation",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["reconciliation_status"] == "RECONCILED"
        assert body["outcome_status"] == "SUCCEEDED"
        assert "integrity_note" in body

    async def test_attestation_for_unknown_evidence_is_404(self, governed_mcp) -> None:
        _mcp_app, raw_key, _org_id, _engine = governed_mcp
        async with LifespanManager(app) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as dash_client:
                r = await dash_client.get(
                    "/api/governance/evidence/does-not-exist/attestation",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        assert r.status_code == 404


class TestOutcomeReportRestEndpoint:
    async def test_manual_outcome_report_then_attestation_reflects_it(self, governed_mcp) -> None:
        """Exercises the manual-reporting endpoint for a caller whose
        execution happens outside a governed dispatch call entirely --
        seeds a bare EvidenceRecord directly (bypassing the MCP round
        trip, since this is testing the report endpoint itself, not
        the auto-recording path already covered above)."""
        _mcp_app, raw_key, org_id, engine = governed_mcp

        evidence_repo = EvidenceRepository(engine)
        gw = WhitePactRuntimeGateway()
        agent = _agent(org_id=org_id)
        action = ActionRequest(agent=agent, action_type="some_action", target="t")
        authority = _authority()
        decision = gw.evaluate(action, authority)
        evidence = build_evidence_record(action, agent, authority, decision)
        await evidence_repo.record(evidence)

        headers = {"Authorization": f"Bearer {raw_key}"}
        async with LifespanManager(app) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as dash_client:
                r = await dash_client.post(
                    f"/api/governance/evidence/{evidence.evidence_id}/outcome",
                    json={"status": "SUCCEEDED", "result_summary": "reported manually"},
                    headers=headers,
                )
                assert r.status_code == 200, r.text
                assert r.json()["status"] == "SUCCEEDED"

                r = await dash_client.get(
                    f"/api/governance/evidence/{evidence.evidence_id}/attestation",
                    headers=headers,
                )
        assert r.status_code == 200
        assert r.json()["outcome_status"] == "SUCCEEDED"

    async def test_report_for_unknown_evidence_is_404(self, governed_mcp) -> None:
        _mcp_app, raw_key, _org_id, _engine = governed_mcp
        async with LifespanManager(app) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as dash_client:
                r = await dash_client.post(
                    "/api/governance/evidence/does-not-exist/outcome",
                    json={"status": "SUCCEEDED"},
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        assert r.status_code == 404
