# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PG/crypto replay race; only schedules two real challenge SELECT results."""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection
from tests.pg_test_url import isolated_pg_url
from tests.test_m13s_security_regression import _register_fake_passkey, _setup_postgres_workspace
from tests.webauthn_fakes import assertion_blob

from responsibleai.db.engine import authority_containment_records, passkey_credentials
from responsibleai.enterprise.authority.service import (
    CustomerAuthorityService,
    compute_canonical_operation_digest,
)
from responsibleai.enterprise.security.webauthn import b64url_decode
from responsibleai.isolation.in_flight import InFlightExecutionRegistry


@pytest.mark.asyncio
async def test_one_zero_counter_assertion_cannot_authorize_two_concurrent_mutations(monkeypatch):
    async for url in isolated_pg_url("wp_m13r2_race"):
        engine, actor, user_id, org_id = await _setup_postgres_workspace(url)
        try:
            private, credential, public = _register_fake_passkey(user_id)
            async with engine.raw.begin() as conn:
                await conn.execute(
                    passkey_credentials.insert().values(
                        id=f"pk_{uuid.uuid4().hex[:12]}",
                        user_id=user_id,
                        credential_id=credential,
                        public_key=public,
                        sign_count=0,
                        rp_id="localhost",
                        transports_json="[]",
                        backup_eligible=1,
                        backup_state=1,
                        display_name="Counterless fixture",
                        status="ACTIVE",
                        created_at=datetime.now(UTC).isoformat(),
                    )
                )
            service = CustomerAuthorityService(engine)
            operation = {
                "org_id": org_id,
                "target_type": "ORGANIZATION",
                "target_id": org_id,
                "containment_action": "LOCKDOWN",
            }
            challenge = await service.create_authority_stepup_challenge(
                actor,
                org_id=org_id,
                action="EMERGENCY_CONTAINMENT",
                operation_digest=compute_canonical_operation_digest(
                    "EMERGENCY_CONTAINMENT", operation
                ),
            )
            client, auth, signature = assertion_blob(
                rp_id="localhost",
                origin=challenge["origin"],
                challenge=b64url_decode(challenge["challenge"]),
                private_key=private,
                sign_count=0,
            )
            assertion = {
                "credential_id": credential,
                "client_data_json": client,
                "authenticator_data": auth,
                "signature": signature,
            }
            monkeypatch.setattr(InFlightExecutionRegistry, "_instance", InFlightExecutionRegistry())
            original_execute = AsyncConnection.execute
            both_read = asyncio.Event()
            reads = 0

            async def schedule_real_select(
                self, statement, *args, _execute=original_execute, _both=both_read, **kwargs
            ):
                nonlocal reads
                result = await _execute(self, statement, *args, **kwargs)
                sql = str(statement)
                if sql.startswith("SELECT") and "FROM authority_step_up_challenges" in sql:
                    reads += 1
                    if reads == 2:
                        _both.set()
                    await asyncio.wait_for(_both.wait(), 10)
                return result

            monkeypatch.setattr(AsyncConnection, "execute", schedule_real_select)
            results = await asyncio.gather(
                *[
                    service.execute_emergency_containment(
                        actor,
                        **operation,
                        reason="Concurrent replay probe",
                        webauthn_assertion=assertion,
                    )
                    for _ in range(2)
                ],
                return_exceptions=True,
            )
            successful = [r for r in results if isinstance(r, dict)]
            assert reads == 2, "Both genuine transactions must reach the challenge-read boundary"
            async with engine.raw.connect() as conn:
                records = await conn.scalar(
                    select(func.count())
                    .select_from(authority_containment_records)
                    .where(authority_containment_records.c.org_id == org_id)
                )
            assert len(successful) == 1 and records == 1, (
                f"One signed challenge produced {len(successful)} successes and {records} committed incidents; must be exactly one"
            )
        finally:
            await engine.raw.dispose()
