"""Concurrent load test for AuditRepository.write() -- the one DB write
that happens on every single API request via AuditLogMiddleware.

BENCHMARKS.md's single-threaded benchmark measured ~0.53ms / ~1,900 ops/sec
for this write in isolation. That number says nothing about what happens
under real concurrent load, because write() holds a single process-wide
asyncio.Lock for its entire duration (hash-chain compute *and* the DB
insert itself) -- by design, since each entry's hash depends on the
previous entry's hash, so writes must be strictly ordered. This script
answers the actual open question: does concurrent request volume get
whatever throughput this lock allows, or does something scale that
naive reasoning would miss?

Not a synthetic estimate -- every number this script prints comes from
an actual run against a real (if in-memory) SQLite-backed AuditRepository,
same as scripts/run_benchmarks.py's own DB benchmark.

Usage: python scripts/loadtest_audit_write.py
"""

from __future__ import annotations

import asyncio
import platform
import sys
import time

sys.path.insert(0, "src")

from sqlalchemy.ext.asyncio import create_async_engine

from responsibleai.db.audit_repository import AuditRepository
from responsibleai.db.engine import DatabaseEngine, metadata
from responsibleai.rbac.models import AuditEntry


async def run_concurrency_level(
    audit_repo: AuditRepository, concurrency: int, total_writes: int
) -> tuple[float, float]:
    """Fire `total_writes` writes using `concurrency` simultaneous coroutines.

    Returns (wall_clock_seconds, writes_per_second).
    """

    remaining = total_writes

    async def worker() -> None:
        nonlocal remaining
        while remaining > 0:
            remaining -= 1
            await audit_repo.write(
                AuditEntry(
                    endpoint="/api/loadtest",
                    method="POST",
                    org_id="loadtest-org",
                    key_id="loadtest-key",
                    status_code=200,
                    duration_ms=1.0,
                )
            )

    start = time.perf_counter()
    await asyncio.gather(*(worker() for _ in range(concurrency)))
    elapsed = time.perf_counter() - start
    return elapsed, total_writes / elapsed


async def main() -> None:
    print(f"Python: {sys.version.split()[0]}  Platform: {platform.platform()}")
    print()
    print("Concurrent AuditRepository.write() throughput, SQLite in-memory.")
    print("Each row fires the same total write count at a different concurrency")
    print("level -- if the chain lock fully serializes writes, throughput should")
    print("stay roughly flat across rows regardless of concurrency; if there's")
    print("real parallel headroom (e.g. in query planning/connection setup before")
    print("the lock is acquired), throughput should rise with concurrency.")
    print()
    print("| Concurrency | Total writes | Wall clock (s) | Writes/sec |")
    print("|---|---|---|---|")

    for concurrency in (1, 5, 10, 25, 50, 100):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        db = DatabaseEngine(engine)
        audit_repo = AuditRepository(db)

        total_writes = max(200, concurrency * 10)
        elapsed, ops_per_sec = await run_concurrency_level(audit_repo, concurrency, total_writes)
        print(f"| {concurrency} | {total_writes} | {elapsed:.4f} | {ops_per_sec:.0f} |")

        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
