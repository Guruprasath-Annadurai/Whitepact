# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable consumption must reject replay, stale epochs and changed context."""

import asyncio
import os
import uuid
from dataclasses import replace

import pytest

from responsibleai.db.approval_repository import ApprovalRepository
from responsibleai.db.engine import create_engine, organizations
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    NonceAlreadyConsumedError,
    StaleRevocationEpochError,
)
from responsibleai.db.revocation_epoch_repository import (
    RevocationEpochRepository,
    bump_epoch_on_connection,
)
from responsibleai.governance.approval import build_approval_request, build_resume_action
from responsibleai.governance.execution import (
    AuthorizationActionMismatchError,
    _validate_authorization,
    authorize_execution,
)
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)


async def _exercise_nonce_race(url):
    engine = create_engine(url)
    await engine.init()
    org = str(uuid.uuid4())
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert().values(id=org, name=org, slug=org, created_at="now")
        )
    nonce = uuid.uuid4().hex
    first = ExecutionNonceRepository(engine)
    second_engine = create_engine(url)
    second = ExecutionNonceRepository(second_engine)
    try:
        results = await asyncio.gather(
            *[
                repo.consume(
                    nonce, authorization_id="permit", organization_id=org, expected_epoch=0
                )
                for repo in [first, second] * 8
            ],
            return_exceptions=True,
        )
        assert sum(result is None for result in results) == 1
        assert sum(isinstance(result, NonceAlreadyConsumedError) for result in results) == 15
        epochs = RevocationEpochRepository(engine)
        assert (await epochs.bump(org, "governance")).epoch == 1
        with pytest.raises(StaleRevocationEpochError):
            await first.consume(
                uuid.uuid4().hex, authorization_id="stale", organization_id=org, expected_epoch=0
            )
        await first.consume(
            uuid.uuid4().hex, authorization_id="fresh", organization_id=org, expected_epoch=1
        )
        # Independent transactions must not lose concurrent increments.
        counters = [epochs, RevocationEpochRepository(second_engine)] * 8
        increments = await asyncio.gather(*[counter.bump(org) for counter in counters])
        assert sorted(item.epoch for item in increments) == list(range(2, 18))
        # A rolled-back authority transaction must roll back its epoch too.
        with pytest.raises(RuntimeError, match="rollback"):
            async with engine.raw.begin() as conn:
                await bump_epoch_on_connection(conn, org)
                raise RuntimeError("rollback")
        assert (await epochs.current(org)).epoch == 17
        # Dispose connection pools and reopen: persisted replay protection survives.
        await second_engine.close()
        restarted_engine = create_engine(url)
        try:
            with pytest.raises(NonceAlreadyConsumedError):
                await ExecutionNonceRepository(restarted_engine).consume(
                    nonce, authorization_id="permit", organization_id=org, expected_epoch=17
                )
        finally:
            await restarted_engine.close()
    finally:
        await second_engine.close()
        await engine.close()


async def test_sqlite_distinct_connections_consume_once(tmp_path):
    await _exercise_nonce_race(str(tmp_path / "nonce.db"))


async def test_postgres_distinct_connections_consume_once():
    url = os.environ.get("WHITEPACT_TEST_POSTGRES_EXECUTION")
    if not url:
        pytest.skip("WHITEPACT_TEST_POSTGRES_EXECUTION requires disposable PostgreSQL")
    await _exercise_nonce_race(url)


@pytest.mark.parametrize(
    "field,value", [("purpose", "other"), ("target", "other"), ("action_type", "write")]
)
def test_permit_rejects_changed_action(field, value):
    action = ActionRequest(
        AgentContext(IdentityContext("a", "api_key", org_id="acme")),
        "read",
        "invoice",
        purpose="reconcile",
    )
    permit = authorize_execution(DecisionResult(GovernanceDecision.ALLOW, action.action_id), action)
    with pytest.raises(AuthorizationActionMismatchError):
        _validate_authorization(permit, replace(action, **{field: value}))


def test_permit_rejects_changed_principal():
    action = ActionRequest(
        AgentContext(IdentityContext("a", "api_key", org_id="acme")), "read", "invoice"
    )
    permit = authorize_execution(DecisionResult(GovernanceDecision.ALLOW, action.action_id), action)
    changed = replace(action, agent=AgentContext(IdentityContext("b", "api_key", org_id="acme")))
    with pytest.raises(AuthorizationActionMismatchError):
        _validate_authorization(permit, changed)


async def test_approval_purpose_survives_database_roundtrip():
    engine = create_engine(":memory:")
    await engine.init()
    try:
        action = ActionRequest(
            AgentContext(IdentityContext("a", "api_key")), "read", "invoice", purpose="reconcile"
        )
        approval = build_approval_request(
            action, DecisionResult(GovernanceDecision.REQUIRE_APPROVAL, action.action_id)
        )
        repo = ApprovalRepository(engine)
        await repo.create(approval)
        restored = await repo.get(approval.approval_id)
        assert restored is not None
        resumed = build_resume_action(restored, agent=action.agent)
        assert resumed.purpose == "reconcile"
        assert restored.matches_action(resumed)
        assert not restored.matches_action(replace(resumed, purpose="other"))
    finally:
        await engine.close()
