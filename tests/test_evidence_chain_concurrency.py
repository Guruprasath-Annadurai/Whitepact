# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Evidence hash chain under concurrent writers, on real PostgreSQL through the real HTTP stack.

A hash chain is a property of storage order. Many requests deciding at once must still yield one
unbroken chain: contiguous sequence numbers, no duplicates, every link verifying, one evidence row per
decision. A race here silently forks or gaps the tamper-evidence the product sells.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select, text

from responsibleai.db import EvidenceRepository, create_engine
from responsibleai.db.engine import governance_evidence
from tests import test_v1_exactly_one_effect as _effect_tests
from tests.test_v1_exactly_one_effect import _prepare_org

journey_client = _effect_tests.journey_client
pg_url = _effect_tests.pg_url

CALLS = 60
PARALLEL = 20


async def test_concurrent_decisions_produce_one_unbroken_chain(
    journey_client, monkeypatch, seed_runtime_authority
) -> None:
    client, pg = journey_client
    org_id, raw = await _prepare_org(client, monkeypatch, seed_runtime_authority, pg)
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    async with engine.raw.begin() as conn:
        await conn.execute(
            text("UPDATE organizations SET plan = 'ENTERPRISE' WHERE id = :i"), {"i": org_id}
        )
        baseline = len((await conn.execute(select(governance_evidence.c.id))).fetchall())

    semaphore = asyncio.Semaphore(PARALLEL)
    headers = {"Authorization": f"Bearer {raw}"}

    async def decide(i: int):
        async with semaphore:
            # No delegated authority for this tool: a DENY decision, which still writes evidence.
            return await client.post(
                "/api/v1/governance/tools/call",
                headers=headers,
                json={"name": "rai_scan", "arguments": {"text": f"x{i}"}, "purpose": "chain race"},
            )

    responses = await asyncio.gather(*(decide(i) for i in range(CALLS)))
    assert all(r.status_code == 200 for r in responses), [r.status_code for r in responses][:10]

    try:
        async with engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(
                        governance_evidence.c.chain_sequence,
                        governance_evidence.c.entry_hash,
                        governance_evidence.c.prev_hash,
                    )
                    .where(governance_evidence.c.org_id == org_id)
                    .order_by(governance_evidence.c.chain_sequence.asc())
                )
            ).fetchall()
        assert len(rows) == baseline + CALLS, "a decision wrote no evidence, or wrote two"
        sequences = [r.chain_sequence for r in rows]
        assert sequences == list(range(1, len(rows) + 1)), "gap or duplicate in chain_sequence"
        assert len({r.entry_hash for r in rows}) == len(rows)
        for previous, current in zip(rows, rows[1:], strict=False):
            assert current.prev_hash == previous.entry_hash, (
                "fork: a record does not link to its predecessor"
            )
        assert await EvidenceRepository(engine).verify_chain(org_id) is True
    finally:
        await engine.close()
