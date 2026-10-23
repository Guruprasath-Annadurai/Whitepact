# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Native PostgreSQL grant/attempt precision, order and restarted-reader proof."""

import asyncio
import json
import os
import subprocess
import sys
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import text

from responsibleai.data_governance import operator_recovery_control as control
from responsibleai.data_governance.backup_defense import (
    RestoreReadinessGate,
    get_restore_readiness_gate,
    set_restore_readiness_gate,
)
from responsibleai.db.engine import create_engine
from responsibleai.runtime.authority_kernel import Phase7AAuthorityKernel
from tests.test_stage3_controller_postgres import controller as controller


@pytest.fixture
async def populated(controller, monkeypatch):
    service, _, owner, token, csrf = controller
    monkeypatch.delenv("WHITEPACT_OPERATOR_RECOVERY_TRUST_CONFIG", raising=False)
    previous = get_restore_readiness_gate()
    set_restore_readiness_gate(
        RestoreReadinessGate(provider=service.provider, db_engine=service.engine)
    )
    try:
        tenants = []
        for index in range(2):
            tenants.append(
                await service.create(
                    session_token=token,
                    csrf=csrf,
                    request_id=f"native-{index}",
                    name=f"Native Tenant {index}",
                    slug=f"native-tenant-{index}",
                )
            )
        grants = []
        for index in range(2):
            grants.append(
                await Phase7AAuthorityKernel(service.engine).issue(
                    organization_id=tenants[0],
                    principal_id=owner,
                    agent_id=owner,
                    identity_id=owner,
                    intent="evidence-only",
                    action_type="test.counter.increment",
                    target="test.counter.increment",
                    action_digest=str(index) * 64,
                    canonical_action_payload="{}",
                    approved_arguments={},
                    idempotency_key=f"native-evidence-{index}",
                )
            )
        yield service, tenants, grants
    finally:
        set_restore_readiness_gate(previous)


@pytest.mark.asyncio
async def test_real_native_rows_repeat_and_restart_with_identical_digests(populated, request):
    service, _, _ = populated
    async with service.engine.raw.connect() as connection:
        forward = [
            dict(row)
            for row in (
                await connection.execute(
                    text(
                        "SELECT * FROM governance_execution_authorizations ORDER BY authorization_id"
                    )
                )
            ).mappings()
        ]
        backward = [
            dict(row)
            for row in (
                await connection.execute(
                    text(
                        "SELECT * FROM governance_execution_authorizations ORDER BY authorization_id DESC"
                    )
                )
            ).mappings()
        ]
        assert len(forward) == len(backward) == 2
        assert type(forward[0]["expires_at"]) is datetime
        assert control._snapshot_digest(forward) == control._snapshot_digest(backward)
        original, _ = await control._pg_snapshots(connection)
        repeated, _ = await control._pg_snapshots(connection)
        assert repeated == original
    fresh = create_engine(service.engine.raw.url.render_as_string(hide_password=False))
    try:
        async with fresh.raw.connect() as connection:
            restarted, _ = await control._pg_snapshots(connection)
            assert restarted == original
    finally:
        await fresh.close()
    child_code = """
import asyncio,json,os,sys
from responsibleai.db.engine import create_engine
from responsibleai.data_governance.operator_recovery_control import _pg_snapshots
async def run():
    engine=create_engine(os.environ['WHITEPACT_EVIDENCE_READER_URL'])
    try:
        async with engine.raw.connect() as connection:
            snapshots,_=await _pg_snapshots(connection)
            print(json.dumps({'version':list(sys.version_info[:2]),'snapshots':snapshots},sort_keys=True))
    finally:
        await engine.close()
asyncio.run(run())
"""
    env = os.environ.copy()
    env["WHITEPACT_EVIDENCE_READER_URL"] = service.engine.raw.url.render_as_string(
        hide_password=False
    )
    readers = [sys.executable]
    other = os.environ.get("WHITEPACT_EVIDENCE_OTHER_PYTHON")
    if other:
        readers.append(other)
    versions = []
    for interpreter in readers:
        result = await asyncio.to_thread(
            subprocess.run,
            [interpreter, "-c", child_code],
            env=env,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, "Independent evidence reader failed; no credentials logged"
        receipt = json.loads(result.stdout)
        assert receipt["snapshots"] == original
        versions.append(receipt["version"])
    if other:
        assert sorted(versions) == [[3, 11], [3, 12]]
    request.node.user_properties.append(("native_digest_reader_versions", json.dumps(versions)))


@pytest.mark.asyncio
async def test_native_authority_and_attempt_mutations_change_digest(populated):
    service, tenants, grants = populated
    mutations = [
        (
            "UPDATE governance_execution_authorizations SET expires_at=expires_at+interval '1 microsecond' WHERE authorization_id=:auth",
            {},
        ),
        (
            "UPDATE governance_execution_authorizations SET oneshot_authority_id=oneshot_authority_id||'-changed' WHERE authorization_id=:auth",
            {},
        ),
        ("UPDATE governance_revocation_epochs SET epoch=epoch+1 WHERE organization_id=:tenant", {}),
        (
            "INSERT INTO governance_execution_nonces(nonce,authorization_id,organization_id,consumed_at) VALUES('nonce-mutated',:auth,:tenant,'2026-10-23')",
            {},
        ),
        ("UPDATE organizations SET name=name||'-changed' WHERE id=:tenant", {}),
        (
            "UPDATE runtime_execution_attempts SET updated_at=updated_at+interval '1 microsecond' WHERE attempt_id=:attempt",
            {},
        ),
        (
            "UPDATE runtime_execution_attempts SET organization_id=:other WHERE attempt_id=:attempt",
            {},
        ),
    ]
    parameters = {
        "auth": grants[0].authorization_id,
        "attempt": grants[0].attempt_id,
        "tenant": tenants[0],
        "other": tenants[1],
    }
    async with service.engine.raw.connect() as connection:
        for statement, _ in mutations:
            transaction = await connection.begin()
            try:
                before, _ = await control._pg_snapshots(connection)
                await connection.execute(text(statement), parameters)
                after, _ = await control._pg_snapshots(connection)
                assert after != before
                assert control._digest(after) != control._digest(before)
            finally:
                await transaction.rollback()  # Disposable fault injection never becomes authority.
        assert (
            await connection.scalar(text("SELECT count(*) FROM test_consequential_counters")) == 0
        )


@pytest.mark.asyncio
async def test_postgres_extended_values_are_not_lossily_converted(controller):
    service, _, _, _, _ = controller
    async with service.engine.raw.connect() as connection:
        values = dict(
            (
                await connection.execute(
                    text("""
            SELECT TIMESTAMPTZ '2026-10-23 01:02:03.000004+05:30' AS aware,
                   TIMESTAMP '2026-10-23 01:02:03.000004' AS naive,
                   DATE '2026-10-23' AS day, TIME '01:02:03.000004' AS clock,
                   TIMETZ '01:02:03.000004+05:30' AS zoned_clock,
                   UUID '00000000-0000-0000-0000-000000000001' AS identity,
                   NUMERIC '9007199254740993.0000000100' AS amount,
                   decode('00ff','hex') AS binary
        """)
                )
            )
            .mappings()
            .one()
        )
    assert type(values["aware"]) is type(values["naive"]) is datetime
    assert type(values["day"]) is date and type(values["clock"]) is time
    assert isinstance(values["identity"], UUID)
    assert values["amount"] == Decimal("9007199254740993.0000000100")
    assert values["binary"] == b"\x00\xff"
    encoded = control._evidence_bytes(values)
    assert encoded == control._evidence_bytes(values)
    assert b"9007199254740993.0000000100" not in encoded  # Decimal tuple, never lossy float/text.
