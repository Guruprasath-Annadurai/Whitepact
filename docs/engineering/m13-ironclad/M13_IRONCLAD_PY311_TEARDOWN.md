# IRONCLAD Python 3.11 teardown diagnosis

Reviewed source checkpoint: 47fc55a1591890f18c06333b4f187d091535719d; tree b57b0e46f388cce8a01690e986fde2be6783a967; parent d480e8c87882a7fc5d353961a6fe22048380ab9f. Initial baseline: 7939341fd9d98d0f1fa39ce4421318dbc1dac33e. Draft PR #221 targets codex/whitepact-m13-absolute-convergence. This is an interim engineering record. Completed d9ddf44a CI is historical relative to this successor; new exact-head CI remains pending.

## Reproduction and limits

Exact793 full matrix: test_plan_scaled_route_limits.py::test_scaling_is_per_organization call passed, app logged shutdown_complete, then asyncio.Runner._cancel_all_tasks gathered indefinitely until original 120-second timeout. Existing faulthandler dump identifies only selector.poll, not the pending coroutine. A Mac/Python 3.11 ordinary-backend6 PASS run does not reproduce Linux/Redis/PostgreSQL conditions.

Source inspection found retry-worker, heartbeat and reconciliation-watcher cancellation without await. None visibly suppresses cancellation forever. They are lifecycle gaps, not an established cause of this hang. No consequential task cancellation change is made speculatively.

Added scripts/engineering/m13_ironclad_task_diagnostics.py temporarily observes the original standard-library cancellation routine. At10/30/60/90 seconds it emits bounded task names, coroutine identities, cancellation counts, waiter state and file/line/function stacks, without locals or arguments. Original cancellation behavior remains; only diagnostic timers are canceled. Two behavioral tests PASS locally3.52 s and focused Ruff passes.

Exact-head Linux job39206376358 runs both interpreters with Redis7/PG16, three isolated repeats of the original file, then the original `7939341f` shard-zero66-file cohort. The checked reference manifest preserves source/inventory identity. Original120-second test limit and1500-second cohort limit remain. Results pending; teardown is NOT FIXED until task ownership and repeated affected-environment success are evidenced.

## Completed d9ddf44a Linux diagnosis

Workflow 39206376358 completed on Ubuntu24.04 with Python 3.11/3.12, Redis7 and PostgreSQL16. Each interpreter: authority63 PASS; route file repeated in three fresh processes,6 PASS each; reference cohort994 cases:988 PASS4 FAIL2 SKIP, **zero teardown ERROR**. Python 3.11 isolated durations7.97 s,7.98 s,8.08 s; cohort377.60 s. Three cohort cancellation-runner entries and one per isolated process completed before the10-second diagnostic snapshot; no pending-task stack was emitted.

Four cohort failures: immutable slash/traversal directory count, NFC-alias assertion, dead-PID unlink assertion, and diagnostic-workflow PLAYWRIGHT_BROWSERS_PATH omission. Last is corrected, pending new-head rerun. The first three remain explicit specification gates. The first diagnostic cohort also omitted the original branch-coverage instrumentation, so it is a runtime comparison rather than a complete reproduction of the original full-matrix conditions. The next cohort restores all three original source coverage scopes and branch tracing. No delayed-task cause has been demonstrated; no lifecycle task cancellation change is claimed as a fix. Diagnostic wrapper now also covers every future full-suite shard with unchanged 120-second cap. One unreproduced failure is not dismissed as flaky.
