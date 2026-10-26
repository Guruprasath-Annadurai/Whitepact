# M13 maintainer-approved assertion dispositions

The maintainer explicitly approved these three scoped dispositions on
2026-10-21. Approval does not cover other protected assertions, migration guards,
callback tests, or the rejected three-second absence proposal.

Baseline HEAD: `71759e44e6c93f412311eaf364f4f1f81c5bec2d`.
Baseline tree: `ab69e61eee378fe6c3f5005f99e30eed193b012d`.
All original test function identifiers are retained. Original source blobs remain
accessible through Git; no historical evidence has been rewritten.

| Original test file | Original Git blob | Approved change |
| --- | --- | --- |
| tests/test_inflight_liveness_adversarial.py | 5b3f1b1ba0d7f5c482a505a5e5902eb29936d101 | ESRCH retains tracking and reports the exact execution/tenant with containment unconfirmed; worker death is not container termination proof. |
| tests/test_h1_collision_invariance.py | e8e948ee1b18e8f4fcdae2f9afc6f6087e881d80 | Distinct NFC/NFD database identifiers retain distinct tracking names. |
| tests/test_h4_backup_recovery_adversarial.py | ccd8d2889df87b97b052c2b8f814521e53607fef | Restored tombstoned tenant is DISABLED; quarantine report/name evidence and API-key/delegation purge assertions remain required. |

## Execution evidence

Python 3.12 before: **3 failed**, each at the precise historical assertion.
Receipt: `/private/tmp/m13-approved-dispositions-before.xml`.
Python 3.12 after: **3 passed**, no skipped cases, 5.84 seconds.
Receipt: `/private/tmp/m13-approved-dispositions-after-py312.xml`.
Python 3.11 after: **3 passed**, no skipped cases, 5.02 seconds.
Receipt: `/private/tmp/m13-approved-dispositions-after-py311.xml`.
The first Python 3.11 invocation had a source-path collection error; rerunning
with explicit `PYTHONPATH=src:.` selected this worktree and passed. That failed
collection is not counted as an executed security test or hidden as a PASS.
These are targeted working-tree results, not whole-platform qualification.

`git diff --check` passes. Ruff passes for the tracking, Unicode and separate
timeout-fixture files. The restored-tenant module retains 23 pre-existing Ruff
findings, reproduced from its exact HEAD blob, and pre-existing formatting drift.
They were not silently waived or mixed into this three-assertion approval.

Product CI at the baseline still has three migration-guard failures (run
39474710654, Python 3.12 job 118807565039): mandatory-passkey downgrade protection
and two expected-head 0065 versus actual 0066 assertions. This approval does not
authorize replacing those assertions; their substantive safety review remains OPEN.

No production implementation changed for these dispositions. No containment
timeout was shortened and no automatic absence-based clearance was added.
Independent qualification and global production remain OPEN / NO-GO.

## Separate approval: runtime compatibility version expectations

On2026-10-22 the founder separately approved updating only the historical
runtime-compatibility test for the journal-enabled runtime. Original file:
`tests/test_m13_runtime_schema_compatibility.py`, Git blob
`d79022add35d0c689b519df96ff6a0675940833e`, at candidate
`f556bb7a6989bfdcf5c2a9ee1961cdf266f8dfe1`.

Before: actual PG16 runtime review39480655583 fails this test on both Python
versions: it expects0066 to be incompatible while the current runtime requires
0066. After change: accept0066; reject0064/0065/0067; attempt0066 inside the
aborted transaction; restore0066 for restart. Existing rollback, incompatible,
restart and missing-version-table assertions remain. Empty/multiple/unreadable
version negatives remain in additive `test_m13_convergence3_schema_contract.py`.
No production code or compatibility allowlist changed under this approval.

The existing dedicated PG16 dual-Python workflow now includes this test alongside
all four historical migration guards. Execution and independent review are
PENDING until exact-head artifacts are collected. Rejecting0065 in the current
runtime is explicitly NOT proof that an older binary cannot use a0066 database.
Old-binary and database-role fencing remain mandatory OPEN requirements.
