# Convergence III — exact revision compatibility repair

Status: PARTIAL. M13 OPEN; GLOBAL PRODUCTION NO-GO.

Starting source: `84710b8d1bbb1503ee4999c117daebe54436d826`, tree
`b5f23fb3d125afa9491226920324b2d5680f4b4e`, direct parent
`71759e44e6c93f412311eaf364f4f1f81c5bec2d`.
The approved assertion commit is already integrated; no cherry-pick or reset.
PR223 was independently queried OPEN/DRAFT at 71759e44 before this repair.

## Reproduction and correction

The 71759e44 runtime introduced a mandatory pre-CREATE journal in migration0066
but retained a startup compatibility allowlist containing only0065. New current
runtime regression cases reproduced **2 FAIL / 5 PASS** on Python3.12:0066
incorrectly rejected and0065 incorrectly accepted. Before receipt:
`/private/tmp/m13-convergence3-schema-before.xml`.

The repaired runtime accepts exactly the singleton revision0066. Empty, old,
future, multiple and unreadable revisions fail closed. No range or generic
forward-compatibility allowance exists. Dashboard startup invokes this guard
before database-backed traffic is initialized. The migration chain remains
0065 ->0066; no0065 passkey DDL or historical assertion changed.

Focused command:
`PYTHONPATH=src:. <python> -m pytest tests/test_m13_convergence3_schema_contract.py -q -o addopts='' --tb=short --junitxml=<receipt>`.

Python3.12: **7 PASS**,2.88s. Python3.11: **7 PASS**,2.62s.
Receipts `/private/tmp/m13-convergence3-schema-after-py312.xml` and
`/private/tmp/m13-convergence3-schema-after-py311.xml`.
These transport-double tests prove revision selection, not PostgreSQL DDL.
Scoped Ruff lint/format and diff checks PASS.

## Real database acceptance

Added `tests/test_m13_convergence3_schema_postgres.py` to the existing native
dual-Python PostgreSQL16 workflow, without deleting any previous test.
It checks0065 rejection, actual upgrade0065->0066, journal existence, rollback
of a controlled revision change, restart, old/future revision rejection and
missing version-table refusal. Execution is PENDING at this report's creation.
This is not a substitute for the complete migration crash/concurrency matrix.

Historical tests `test_m13_runtime_schema_compatibility.py` and
`test_m13_apex_migration_guard.py` remain intact. Their fixed0065 expectations
need separately reviewed historical-version fixtures or explicit disposition;
they are not counted as passing via the new tests.

## Safety limits and outstanding evidence

0066 downgrade refuses any journal rows, including terminal evidence. Its DDL
is not proof of old-binary fencing: earlier binaries may lack the schema guard.
Actual legacy-role retirement, old-binary attempts, concurrent migration,
interrupted DDL, permission failures, mandatory-passkey downgrade safety and
recovery after upgrade failure remain mandatory OPEN tests/operational controls.
No database permission or destructive migration operation was performed locally.

Prior exact71759e44 native evidence is run39474701876:27 unit,2 cold-restart,
19 native cases passed per interpreter. Those results belong to71759e44, not
this uncommitted repair. No successor CI or independent qualification is claimed.
