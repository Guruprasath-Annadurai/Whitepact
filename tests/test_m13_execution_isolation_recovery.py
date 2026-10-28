# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Twenty reconstruction scenarios; backend simulations are not containment proof.

Every durable_case receipt is stored in JUnit properties. The native case is
explicitly skipped unless a real supported host and approved runtime exist.
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import insert, select

from responsibleai.db import ApprovalNotApprovedError, ApprovalRepository, create_engine
from responsibleai.db.engine import governance_execution_nonces, governance_outcomes, organizations
from responsibleai.db.execution_nonce_repository import ExecutionNonceRepository
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.governance.approval import ApprovalStatus, build_approval_request
from responsibleai.governance.execution import InternalToolExecutor
from responsibleai.governance.models import DecisionResult, GovernanceDecision
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.errors import (
    IsolationBackendUnavailableError,
    IsolationExecutionUncertainError,
    IsolationFilesystemPermissionError,
    IsolationRuntimeUnavailableError,
)
from responsibleai.mcp.governance_integration import (
    ApprovalAuthorizationDeniedError,
    resume_approval,
)
from tests.test_m13_windows_isolation_recovery import (
    action,
    recovery_engine,  # noqa: F401 -- pytest fixtures
    restore_boundary,  # noqa: F401
    resume_case,  # noqa: F401
)


async def snapshot(case):
    async with case.engine.raw.connect() as conn:
        nonces = (await conn.execute(select(governance_execution_nonces))).mappings().all()
        outcomes = (await conn.execute(select(governance_outcomes))).mappings().all()
    approval = await case.repo.get(case.id)
    return {
        "approval": approval.status.value,
        "nonce_count": len(nonces),
        "nonces": [dict(row) for row in nonces],
        "outcomes": [dict(row) for row in outcomes],
    }


@pytest.fixture
async def durable_case(resume_case, monkeypatch, record_property):  # noqa: F811
    case = resume_case
    org = case.kwargs["org_id"]
    if case.engine.raw.dialect.name == "sqlite":
        # Explicit disposable unit-test tenant only. PG uses protected onboarding.
        async with case.engine.raw.begin() as conn:
            await conn.execute(
                insert(organizations).values(
                    id=org,
                    name="P0 test",
                    slug="p0-test",
                    governance_status="ACTIVE",
                    created_at=datetime.now(UTC).isoformat(),
                )
            )
    case.nonces = ExecutionNonceRepository(case.engine)
    case.kwargs["nonce_repo"] = case.nonces
    case.kwargs["epoch_repo"] = RevocationEpochRepository(case.engine)
    executor = InternalToolExecutor(broker=case.broker, nonce_repo=case.nonces)
    monkeypatch.setattr(
        "responsibleai.mcp.governance_integration.InternalToolExecutor", lambda **kwargs: executor
    )
    case.fault = "unset"
    case.possible_execution = False
    case.http = "NOT_INVOKED: direct service test"
    initial = await snapshot(case)
    yield case
    final = await snapshot(case)
    record_property(
        "security_receipt",
        json.dumps(
            {
                "initial": initial,
                "fault": case.fault,
                "external_execution_may_have_started": case.possible_execution,
                "backend_mocked": True,
                "final": final,
                "http": case.http,
                "eligibility": "reconciliation required"
                if final["nonce_count"]
                else "fresh authorization required if consumed; original approval never reset",
                "database": case.engine.raw.dialect.name,
            },
            default=str,
        ),
    )


async def blocked(case, fault):
    case.fault = fault
    case.broker.preflight.side_effect = IsolationFilesystemPermissionError("host diagnostic")
    with pytest.raises(IsolationRuntimeUnavailableError):
        await resume_approval(case.id, **case.kwargs)
    state = await snapshot(case)
    assert state["approval"] == "CONSUMED" and state["nonce_count"] == 0
    assert [row["status"] for row in state["outcomes"]] == ["BLOCKED"]
    case.broker.execute.assert_not_awaited()


async def uncertain(case, fault, error=None):
    case.fault = fault
    case.possible_execution = True
    case.broker.execute.side_effect = error or IsolationBackendUnavailableError("lost runtime")
    with pytest.raises(IsolationExecutionUncertainError):
        await resume_approval(case.id, **case.kwargs)
    state = await snapshot(case)
    assert state["approval"] == "CONSUMED" and state["nonce_count"] == 1
    assert [row["status"] for row in state["outcomes"]] == ["UNKNOWN"]


async def test_01_setfacl_missing(durable_case, tmp_path, monkeypatch):
    from responsibleai.isolation import filesystem

    path = tmp_path / "trusted-runner"
    path.write_text("trusted")
    monkeypatch.setattr(filesystem.shutil, "which", lambda _: None)
    monkeypatch.setattr(filesystem.os, "geteuid", lambda: 1000, raising=False)
    durable_case.fault = "real grant helper, simulated missing ACL/nonroot"
    durable_case.broker.preflight.side_effect = lambda: filesystem.grant_container_read(path)
    try:
        with pytest.raises(IsolationRuntimeUnavailableError):
            await resume_approval(durable_case.id, **durable_case.kwargs)
        state = await snapshot(durable_case)
        assert state["nonce_count"] == 0 and state["outcomes"][0]["status"] == "BLOCKED"
    finally:
        path.chmod(0o600)


async def test_02_docker_daemon_unavailable(durable_case, monkeypatch):
    case = durable_case
    case.fault = "canonical lazy constructor, Docker info unavailable"
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    monkeypatch.setattr(DockerContainerBackend, "is_available", lambda _: False)
    monkeypatch.setattr(
        "responsibleai.mcp.governance_integration.InternalToolExecutor", InternalToolExecutor
    )
    with pytest.raises(IsolationRuntimeUnavailableError):
        await resume_approval(case.id, **case.kwargs)
    state = await snapshot(case)
    assert state["approval"] == "CONSUMED" and state["nonce_count"] == 0
    assert state["outcomes"][0]["status"] == "BLOCKED"


async def test_03_nonroot_runner_permission_denied(durable_case):
    await blocked(durable_case, "nonroot trusted runner mapping refused")


async def test_04_daemon_disappears_after_preflight(durable_case):
    await uncertain(durable_case, "preflight succeeds; backend loses daemon")


async def test_05_failure_before_nonce_admission(durable_case):
    await blocked(durable_case, "capability refusal before durable admission")


async def test_06_failure_after_admission(durable_case):
    await uncertain(durable_case, "backend failure after real nonce transaction")


async def test_07_approval_consumed_before_probe(durable_case):
    case = durable_case
    case.fault = "probe reads actual committed approval through separate thread"
    loop = asyncio.get_running_loop()

    def probe():
        future = asyncio.run_coroutine_threadsafe(case.repo.get(case.id), loop)
        assert future.result(timeout=10).status == ApprovalStatus.CONSUMED
        raise IsolationFilesystemPermissionError("refusal")

    case.broker.preflight.side_effect = probe
    with pytest.raises(IsolationRuntimeUnavailableError):
        await resume_approval(case.id, **case.kwargs)
    assert (await snapshot(case))["nonce_count"] == 0


async def test_08_consumed_approval_replay(durable_case):
    await blocked(durable_case, "repeat execution after blocked consumed approval")
    with pytest.raises(ApprovalNotApprovedError):
        await resume_approval(durable_case.id, **durable_case.kwargs)
    assert (await snapshot(durable_case))["nonce_count"] == 0


async def test_09_concurrent_resume_one_winner(durable_case):
    case = durable_case
    case.fault = "two concurrent service attempts"
    case.possible_execution = True  # simulated backend only
    result = await asyncio.gather(
        resume_approval(case.id, **case.kwargs),
        resume_approval(case.id, **case.kwargs),
        return_exceptions=True,
    )
    assert sum(isinstance(item, dict) for item in result) == 1
    assert sum(isinstance(item, ApprovalNotApprovedError) for item in result) == 1
    state = await snapshot(case)
    assert state["nonce_count"] == 1 and state["approval"] == "CONSUMED"
    case.broker.execute.assert_awaited_once()


async def _file_case(path, selected_engine):
    if os.environ.get("WHITEPACT_P0_TEST_POSTGRES") == "1":
        engine, org_id = selected_engine
        database = engine.raw.url.render_as_string(hide_password=False)
    else:
        engine = create_engine(str(path))
        database = str(path)
        org_id = "tenant"
        await engine.init()
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(organizations).values(
                    id=org_id,
                    name="worker test",
                    slug="worker-test",
                    governance_status="ACTIVE",
                    created_at=datetime.now(UTC).isoformat(),
                )
            )
    repo = ApprovalRepository(engine)
    request = action(org_id)
    saved = await repo.create(
        build_approval_request(
            request, DecisionResult(GovernanceDecision.REQUIRE_APPROVAL, request.action_id)
        )
    )
    await repo.resolve(saved.approval_id, resolved_by="human", outcome=ApprovalStatus.APPROVED)
    return SimpleNamespace(engine=engine, repo=repo, id=saved.approval_id, database=database)


def worker_main():
    """Real separate interpreter; a deliberate crash leaves committed state."""
    approval_id, mode = sys.argv[1:]

    async def run():
        engine = create_engine(os.environ["WHITEPACT_WORKER_TEST_DATABASE"])
        try:
            approval = await ApprovalRepository(engine).get(approval_id)
            if approval is None:
                raise AssertionError("Worker approval missing")
            org_id = approval.organization_id
            epoch = (await RevocationEpochRepository(engine).current(org_id)).epoch
            if mode != "nonce-replay":
                await ApprovalRepository(engine).consume(approval_id, action=action(org_id))
            await ExecutionNonceRepository(engine).consume(
                "worker-nonce",
                authorization_id="worker-permit",
                organization_id=org_id,
                expected_epoch=epoch,
            )
            if mode == "crash":
                os._exit(23)
            print("ADMITTED", flush=True)
        except Exception as error:
            print(type(error).__name__, flush=True)
        finally:
            await engine.close()

    asyncio.run(run())


def _worker(database, approval, mode):
    worker_env = dict(os.environ, WHITEPACT_WORKER_TEST_DATABASE=database)
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from tests.test_m13_execution_isolation_recovery import worker_main; worker_main()",
            approval,
            mode,
        ],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
        env=worker_env,
    )


async def test_10_separate_worker_processes(tmp_path, record_property, recovery_engine):  # noqa: F811
    case = await _file_case(tmp_path / "workers.db", recovery_engine)
    try:
        initial = await snapshot(case)
        results = await asyncio.gather(
            asyncio.to_thread(_worker, case.database, case.id, "run"),
            asyncio.to_thread(_worker, case.database, case.id, "run"),
        )
        assert sorted(item.stdout.strip() for item in results) == [
            "ADMITTED",
            "ApprovalNotApprovedError",
        ]
        final = await snapshot(case)
        assert final["approval"] == "CONSUMED" and final["nonce_count"] == 1
        record_property(
            "security_receipt",
            json.dumps(
                {
                    "initial": initial,
                    "final": final,
                    "fault": "separate workers race approval",
                    "http": "NOT_INVOKED",
                    "execution": "admission only, no external side effect",
                    "eligibility": "reconcile missing outcome",
                    "database": case.engine.raw.dialect.name,
                },
                default=str,
            ),
        )
    finally:
        await case.engine.close()


async def test_11_nonce_replay_after_process_crash(tmp_path, record_property, recovery_engine):  # noqa: F811
    path = tmp_path / "crash.db"
    case = await _file_case(path, recovery_engine)
    try:
        initial = await snapshot(case)
        crash = await asyncio.to_thread(_worker, case.database, case.id, "crash")
        assert crash.returncode == 23
        replay = await asyncio.to_thread(_worker, case.database, case.id, "nonce-replay")
        assert replay.stdout.strip() == "NonceAlreadyConsumedError"
        final = await snapshot(case)
        assert final["approval"] == "CONSUMED" and final["nonce_count"] == 1
        assert final["outcomes"] == []  # missing outcome requires reconciliation
        record_property(
            "security_receipt",
            json.dumps(
                {
                    "initial": initial,
                    "final": final,
                    "fault": "worker crashes after committed nonce",
                    "http": "NOT_INVOKED",
                    "eligibility": "reconcile; never replay",
                    "execution": "no tool dispatched",
                    "database": case.engine.raw.dialect.name,
                },
                default=str,
            ),
        )
    finally:
        await case.engine.close()


async def test_12_lost_create_acknowledgement(durable_case, monkeypatch, tmp_path):
    backend = DockerContainerBackend()
    monkeypatch.setattr(
        "responsibleai.isolation.container_backend.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout="untrusted acknowledgement"),
    )
    monkeypatch.setattr(backend, "_trusted_container_id", lambda _: "a" * 64)
    with pytest.raises(IsolationBackendUnavailableError):
        backend._create_stopped_container(["docker", "create"], tmp_path / "cid")
    await uncertain(durable_case, "lost CREATE acknowledgement; START not proven")


async def test_13_container_start_uncertainty(durable_case):
    await uncertain(durable_case, "START sent; acknowledgement lost", OSError("connection lost"))


async def test_14_evidence_database_outage(durable_case):
    case = durable_case
    case.fault = "evidence persistence raises before approval consumption"
    case.kwargs["evidence_repo"] = SimpleNamespace(
        record=AsyncMock(side_effect=OSError("db unavailable"))
    )
    with pytest.raises(ApprovalAuthorizationDeniedError):
        await resume_approval(case.id, **case.kwargs)
    state = await snapshot(case)
    assert state["approval"] == "APPROVED" and state["nonce_count"] == 0 and not state["outcomes"]


async def test_15_outcome_database_outage(durable_case):
    case = durable_case
    case.fault = "pre-admission refusal then outcome persistence outage"
    case.broker.preflight.side_effect = IsolationFilesystemPermissionError("no ACL")
    case.kwargs["outcome_repo"] = SimpleNamespace(
        record=AsyncMock(side_effect=OSError("db unavailable"))
    )
    with pytest.raises(IsolationExecutionUncertainError):
        await resume_approval(case.id, **case.kwargs)
    state = await snapshot(case)
    assert state["approval"] == "CONSUMED" and state["nonce_count"] == 0 and not state["outcomes"]
    with pytest.raises(ApprovalNotApprovedError):
        await resume_approval(case.id, **case.kwargs)


async def test_16_cross_tenant_attempt(durable_case):
    from responsibleai.db import ApprovalNotFoundError

    case = durable_case
    case.fault = "another tenant attempts approval ID"
    with pytest.raises(ApprovalNotFoundError):
        await resume_approval(case.id, **dict(case.kwargs, org_id="other-tenant"))
    state = await snapshot(case)
    assert state["approval"] == "APPROVED" and state["nonce_count"] == 0
    case.broker.execute.assert_not_awaited()


async def test_17_revocation_between_approval_and_execution(durable_case):
    case = durable_case
    case.fault = "durable revocation epoch advances before resume"
    await case.kwargs["epoch_repo"].bump(case.kwargs["org_id"])
    with pytest.raises(ApprovalAuthorizationDeniedError):
        await resume_approval(case.id, **case.kwargs)
    state = await snapshot(case)
    assert state["approval"] == "APPROVED" and state["nonce_count"] == 0
    case.broker.execute.assert_not_awaited()


async def test_18_sanitized_http_503(durable_case):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from responsibleai.dashboard.app import isolation_unavailable_handler

    case = durable_case
    case.fault = "HTTP wrapper around real resume path; injected host permission refusal"
    case.broker.preflight.side_effect = IsolationFilesystemPermissionError(
        "C:/host/private token=secret"
    )
    app = FastAPI()
    app.add_exception_handler(IsolationRuntimeUnavailableError, isolation_unavailable_handler)

    @app.post("/execute")
    async def execute():
        return await resume_approval(case.id, **case.kwargs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/execute")
    case.http = response.json()
    assert response.status_code == 503 and response.json()["execution_status"] == "BLOCKED"
    assert "secret" not in response.text and "private" not in response.text
    assert "fresh authorized request" in response.text


@pytest.mark.usefixtures("real_container_host")
async def test_19_real_contained_execution(record_property):
    from tests.docker_runtime import require_container_isolation_host

    require_container_isolation_host()
    image = os.environ.get("WHITEPACT_TEST_RUNTIME_IMAGE")
    if not image:
        pytest.skip("Approved runtime image unavailable; real containment NOT EXECUTED")
    # Reuse the unchanged native historical assertion, not a mock result.
    from _pytest.monkeypatch import MonkeyPatch

    from tests.test_isolation_real_tool_e2e import TestRealContainerExecution

    with MonkeyPatch.context() as environment:
        await TestRealContainerExecution().test_a_real_tool_executes_in_a_container_and_matches_in_process(
            environment
        )
    record_property(
        "security_receipt",
        json.dumps(
            {
                "backend_mocked": False,
                "execution": "historical native Docker assertion passed",
                "approval": "NOT_APPLICABLE: direct permit test",
                "nonce": "NOT_APPLICABLE: historical direct permit",
                "http": "NOT_INVOKED",
            }
        ),
    )


async def test_20_fresh_human_authorization_after_block(durable_case):
    case = durable_case
    await blocked(case, "original request blocked; fresh explicit human approval follows")
    old = await case.repo.get(case.id)
    request = action(case.kwargs["org_id"])
    current_epoch = (await case.kwargs["epoch_repo"].current(case.kwargs["org_id"])).epoch
    fresh = await case.repo.create(
        build_approval_request(
            request,
            DecisionResult(GovernanceDecision.REQUIRE_APPROVAL, request.action_id),
            authentication_method="api_key",
            revocation_epoch=current_epoch,
            authority_version="v1",
        )
    )
    await case.repo.resolve(
        fresh.approval_id, resolved_by="fresh-human", outcome=ApprovalStatus.APPROVED
    )
    assert fresh.approval_id != old.approval_id
    case.broker.preflight.side_effect = None
    await resume_approval(fresh.approval_id, **case.kwargs)
    assert (await case.repo.get(old.approval_id)).status == ApprovalStatus.CONSUMED
    assert (await case.repo.get(fresh.approval_id)).status == ApprovalStatus.CONSUMED
    state = await snapshot(case)
    assert state["nonce_count"] == 1
    assert sorted(row["status"] for row in state["outcomes"]) == ["BLOCKED", "SUCCEEDED"]


async def test_21_cancellation_preserves_unknown_and_propagates(durable_case):
    case = durable_case
    case.fault = "cancellation after real nonce admission"
    case.possible_execution = True
    case.broker.execute.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await resume_approval(case.id, **case.kwargs)
    state = await snapshot(case)
    assert state["approval"] == "CONSUMED" and state["nonce_count"] == 1
    assert state["outcomes"][0]["status"] == "UNKNOWN"
    with pytest.raises(ApprovalNotApprovedError):
        await resume_approval(case.id, **case.kwargs)
