# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""New reconstruction tests. Mocked isolation is NOT containment evidence."""

import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import select

from responsibleai.db import ApprovalNotApprovedError, ApprovalRepository, create_engine
from responsibleai.db.engine import governance_outcomes
from responsibleai.db.evidence_repository import EvidenceRepository
from responsibleai.db.outcome_repository import OutcomeRepository
from responsibleai.governance.approval import ApprovalStatus, build_approval_request
from responsibleai.governance.execution import InternalToolExecutor, authorize_execution
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.isolation.broker import IsolationBroker
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.errors import (
    IsolationBackendUnavailableError,
    IsolationExecutionUncertainError,
    IsolationFilesystemPermissionError,
    IsolationRuntimeUnavailableError,
)
from responsibleai.isolation.filesystem import grant_container_read
from responsibleai.mcp.governance_integration import resume_approval


def action(org_id="tenant"):
    return ActionRequest(
        AgentContext(
            IdentityContext("requester", "api_key", org_id=org_id), organization_id=org_id
        ),
        "rai_health",
        "rai_health",
        arguments={},
        purpose="test only",
    )


@pytest.fixture(autouse=True)
def restore_boundary(monkeypatch, request):
    if "real_container_host" in request.fixturenames:
        return
    # Isolate executor state transitions from Store B qualification, which is
    # explicitly outside these mocked tests. Production gate remains untouched.
    monkeypatch.setattr(
        "responsibleai.data_governance.backup_defense.assert_current_restore_readiness_admitted",
        AsyncMock(),
    )


@pytest.mark.parametrize(
    "error",
    [
        IsolationFilesystemPermissionError("/private/host secret"),
        IsolationBackendUnavailableError("daemon secret"),
        PermissionError("host path"),
    ],
)
async def test_preflight_refusal_never_spends_nonce_or_dispatches(error):
    broker = SimpleNamespace(preflight=Mock(side_effect=error), execute=AsyncMock())
    nonces = SimpleNamespace(consume=AsyncMock())
    request = action()
    permit = authorize_execution(
        DecisionResult(GovernanceDecision.ALLOW, request.action_id), request, revocation_epoch=0
    )
    with pytest.raises(IsolationRuntimeUnavailableError) as caught:
        await InternalToolExecutor(broker=broker, nonce_repo=nonces).execute(permit, request)
    assert "secret" not in str(caught.value) and "/private" not in str(caught.value)
    assert not permit.consumed
    nonces.consume.assert_not_awaited()
    broker.execute.assert_not_awaited()


async def test_backend_loss_after_admission_is_uncertain_even_for_preflight_error_type():
    broker = SimpleNamespace(
        preflight=Mock(),
        execute=AsyncMock(side_effect=IsolationRuntimeUnavailableError("lost after probe")),
    )
    nonces = SimpleNamespace(consume=AsyncMock())
    request = action()
    permit = authorize_execution(
        DecisionResult(GovernanceDecision.ALLOW, request.action_id), request, revocation_epoch=0
    )
    with pytest.raises(IsolationExecutionUncertainError):
        await InternalToolExecutor(broker=broker, nonce_repo=nonces).execute(permit, request)
    assert permit.consumed
    nonces.consume.assert_awaited_once()
    broker.execute.assert_awaited_once()


async def test_mock_success_orders_probe_before_nonce_before_dispatch():
    events = []

    async def consume(*args, **kwargs):
        events.append("nonce")

    async def execute(*args):
        events.append("execute")
        return {"ok": True}

    broker = SimpleNamespace(preflight=lambda: events.append("probe"), execute=execute)
    request = action()
    permit = authorize_execution(
        DecisionResult(GovernanceDecision.ALLOW, request.action_id), request, revocation_epoch=0
    )
    assert await InternalToolExecutor(
        broker=broker, nonce_repo=SimpleNamespace(consume=consume)
    ).execute(permit, request) == {"ok": True}
    assert events == ["probe", "nonce", "execute"]


def test_missing_setfacl_nonroot_refuses_without_world_readable_fallback(tmp_path, monkeypatch):
    from responsibleai.isolation import filesystem

    path = tmp_path / "runner"
    path.write_text("trusted")
    monkeypatch.setattr(filesystem.shutil, "which", lambda name: None)
    monkeypatch.setattr(filesystem.os, "geteuid", lambda: 1000, raising=False)
    try:
        with pytest.raises(IsolationFilesystemPermissionError):
            grant_container_read(path)
    finally:
        path.chmod(0o600)


def test_docker_preflight_refuses_daemon_loss_without_creating_container(monkeypatch):
    backend = DockerContainerBackend()
    monkeypatch.setattr(backend, "is_available", lambda: False)
    create = Mock(side_effect=AssertionError("must not create"))
    monkeypatch.setattr(backend, "_create_stopped_container", create)
    with pytest.raises(IsolationBackendUnavailableError):
        backend.preflight()
    create.assert_not_called()


def test_broker_checks_selected_backend_availability():
    backend = SimpleNamespace(is_available=lambda: False)
    with pytest.raises(IsolationBackendUnavailableError):
        IsolationBroker(backend=backend).preflight()


@pytest.fixture
async def recovery_engine(tmp_path, monkeypatch):
    if os.environ.get("WHITEPACT_P0_TEST_POSTGRES") == "1":
        from contextlib import aclosing

        from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
        from responsibleai.db.web_identity_repository import WebIdentityRepository
        from tests.pg_test_url import isolated_pg_url
        from tests.protected_component_tenant import (
            authorized_workspace,
            bind_component_controller_scope,
            create_controlled_engine,
        )

        async with aclosing(isolated_pg_url("wp_p0_isolation")) as databases:
            async for url in databases:
                await _run_alembic(_find_alembic_ini(), _migration_env(url), "upgrade", "head")
                async with bind_component_controller_scope(tmp_path, monkeypatch):
                    engine = await create_controlled_engine(url)
                    identities = WebIdentityRepository(engine)
                    uid, verification = await identities.register(
                        "P0 Test Owner", "p0-owner@example.com", "TestPassword123!@#"
                    )
                    await identities.verify_email(verification)
                    org = await authorized_workspace(engine, uid, name="P0 Test", slug="p0-test")
                    yield engine, org["id"] if isinstance(org, dict) else org.id
        return
    engine = create_engine(":memory:")
    await engine.init()
    try:
        yield engine, "tenant"
    finally:
        await engine.close()


@pytest.fixture
async def resume_case(monkeypatch, recovery_engine):
    from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository

    engine, org_id = recovery_engine
    initial_epoch = (await RevocationEpochRepository(engine).current(org_id)).epoch
    repo = ApprovalRepository(engine)
    request = action(org_id)
    verdict = DecisionResult(GovernanceDecision.REQUIRE_APPROVAL, request.action_id)
    saved = await repo.create(
        build_approval_request(
            request,
            verdict,
            authentication_method="api_key",
            revocation_epoch=initial_epoch,
            authority_version="v1",
        )
    )
    await repo.resolve(saved.approval_id, resolved_by="human", outcome=ApprovalStatus.APPROVED)
    nonces = SimpleNamespace(consume=AsyncMock())
    broker = SimpleNamespace(preflight=Mock(), execute=AsyncMock(return_value={"ok": True}))
    real_executor = InternalToolExecutor(broker=broker, nonce_repo=nonces)
    monkeypatch.setattr(
        "responsibleai.mcp.governance_integration.InternalToolExecutor",
        lambda **kwargs: real_executor,
    )
    authority = AuthorityContext(
        delegated_by=org_id, granted_action_types=frozenset({"rai_health"})
    )
    kwargs = dict(
        approval_repo=repo,
        evidence_repo=EvidenceRepository(engine),
        org_id=org_id,
        outcome_repo=OutcomeRepository(engine),
        nonce_repo=nonces,
        epoch_repo=SimpleNamespace(
            current=AsyncMock(return_value=SimpleNamespace(epoch=initial_epoch))
        ),
        authority_resolver=SimpleNamespace(
            resolve=AsyncMock(
                return_value=SimpleNamespace(
                    authority=authority,
                    authority_version="v1",
                    consent_id="consent",
                    consent_version="v1",
                )
            )
        ),
        policy_repo=SimpleNamespace(get_policy=AsyncMock(return_value=SimpleNamespace(version=1))),
        gateway=SimpleNamespace(
            evaluate=lambda *args, **kw: DecisionResult(
                GovernanceDecision.REQUIRE_APPROVAL, request.action_id
            )
        ),
    )
    yield SimpleNamespace(
        engine=engine, repo=repo, id=saved.approval_id, broker=broker, nonces=nonces, kwargs=kwargs
    )


@pytest.mark.parametrize("before", [True, False])
async def test_resume_persists_distinct_failure_and_keeps_approval_consumed(resume_case, before):
    case = resume_case
    if before:

        def refuse():
            # Approval consumption must already have committed when probing.
            raise IsolationFilesystemPermissionError("host secret")

        case.broker.preflight.side_effect = refuse
    else:
        case.broker.execute.side_effect = IsolationBackendUnavailableError("lost daemon")
    with pytest.raises(
        IsolationRuntimeUnavailableError if before else IsolationExecutionUncertainError
    ):
        await resume_approval(case.id, **case.kwargs)
    assert (await case.repo.get(case.id)).status == ApprovalStatus.CONSUMED
    async with case.engine.raw.connect() as conn:
        status = (await conn.execute(select(governance_outcomes.c.status))).scalar_one()
    assert status == ("BLOCKED" if before else "UNKNOWN")
    with pytest.raises(ApprovalNotApprovedError):
        await resume_approval(case.id, **case.kwargs)
    assert case.nonces.consume.await_count == (0 if before else 1)
    assert case.broker.execute.await_count == (0 if before else 1)


async def test_pre_execution_evidence_failure_never_consumes_or_probes(resume_case):
    from responsibleai.mcp.governance_integration import ApprovalAuthorizationDeniedError

    case = resume_case
    case.kwargs["evidence_repo"] = SimpleNamespace(record=AsyncMock(side_effect=OSError("db down")))
    with pytest.raises(ApprovalAuthorizationDeniedError):
        await resume_approval(case.id, **case.kwargs)
    assert (await case.repo.get(case.id)).status == ApprovalStatus.APPROVED
    case.broker.preflight.assert_not_called()
    case.nonces.consume.assert_not_awaited()


async def test_concurrent_resume_has_one_dispatch_winner(resume_case):
    case = resume_case
    results = await asyncio.gather(
        resume_approval(case.id, **case.kwargs),
        resume_approval(case.id, **case.kwargs),
        return_exceptions=True,
    )
    assert sum(isinstance(result, ApprovalNotApprovedError) for result in results) == 1
    assert sum(isinstance(result, dict) for result in results) == 1
    case.nonces.consume.assert_awaited_once()
    case.broker.execute.assert_awaited_once()


async def test_canonical_constructor_daemon_loss_is_recorded_after_approval_consumption(
    resume_case, monkeypatch
):
    case = resume_case
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    monkeypatch.setattr(DockerContainerBackend, "is_available", lambda self: False)
    # Undo the test-injected executor: exercise canonical lazy initialization.
    monkeypatch.setattr(
        "responsibleai.mcp.governance_integration.InternalToolExecutor", InternalToolExecutor
    )
    with pytest.raises(IsolationRuntimeUnavailableError):
        await resume_approval(case.id, **case.kwargs)
    assert (await case.repo.get(case.id)).status == ApprovalStatus.CONSUMED
    case.nonces.consume.assert_not_awaited()
    async with case.engine.raw.connect() as conn:
        assert (await conn.execute(select(governance_outcomes.c.status))).scalar_one() == "BLOCKED"


async def test_nonce_admission_failure_never_dispatches():
    broker = SimpleNamespace(preflight=Mock(), execute=AsyncMock())
    nonces = SimpleNamespace(consume=AsyncMock(side_effect=RuntimeError("admission denied")))
    request = action()
    permit = authorize_execution(
        DecisionResult(GovernanceDecision.ALLOW, request.action_id), request, revocation_epoch=0
    )
    with pytest.raises(RuntimeError, match="admission denied"):
        await InternalToolExecutor(broker=broker, nonce_repo=nonces).execute(permit, request)
    broker.execute.assert_not_awaited()
    assert not permit.consumed


async def test_outcome_write_failure_never_reopens_consumed_approval(resume_case):
    case = resume_case
    case.broker.preflight.side_effect = IsolationFilesystemPermissionError("no ACL")
    case.kwargs["outcome_repo"] = SimpleNamespace(record=AsyncMock(side_effect=OSError("db down")))
    with pytest.raises(IsolationExecutionUncertainError):
        await resume_approval(case.id, **case.kwargs)
    with pytest.raises(ApprovalNotApprovedError):
        await resume_approval(case.id, **case.kwargs)
    assert (await case.repo.get(case.id)).status == ApprovalStatus.CONSUMED
    case.nonces.consume.assert_not_awaited()


async def test_windows_local_backend_refuses_execution(monkeypatch):
    from responsibleai.isolation.subprocess_backend import LocalSubprocessBackend

    backend = LocalSubprocessBackend()
    monkeypatch.setattr(backend, "is_available", lambda: False)
    with pytest.raises(IsolationBackendUnavailableError):
        await backend.execute(None)


def test_http_handler_registration_does_not_mislabel_policy_denials():
    from responsibleai.dashboard.app import app, isolation_unavailable_handler
    from responsibleai.isolation.errors import IsolationError, IsolationPolicyViolationError

    assert IsolationError not in app.exception_handlers
    assert IsolationPolicyViolationError not in app.exception_handlers
    assert app.exception_handlers[IsolationRuntimeUnavailableError] is isolation_unavailable_handler
    assert app.exception_handlers[IsolationExecutionUncertainError] is isolation_unavailable_handler


@pytest.mark.parametrize("before", [True, False])
async def test_http_isolation_errors_are_sanitized(before):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from responsibleai.dashboard.app import isolation_unavailable_handler
    from responsibleai.isolation.errors import IsolationError

    app = FastAPI()
    app.add_exception_handler(IsolationError, isolation_unavailable_handler)

    @app.get("/execute")
    async def execute():
        error = IsolationRuntimeUnavailableError if before else IsolationExecutionUncertainError
        raise error("C:/private/host token=secret")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/execute")
    assert response.status_code == 503
    assert response.json()["code"] == "ISOLATION_RUNTIME_UNAVAILABLE"
    assert response.json()["execution_status"] == ("BLOCKED" if before else "UNKNOWN")
    assert "secret" not in json.dumps(response.json())
    assert "private" not in json.dumps(response.json())
