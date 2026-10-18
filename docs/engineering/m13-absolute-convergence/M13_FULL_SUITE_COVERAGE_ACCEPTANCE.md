# M13 full suite and coverage acceptance

Tested source HEAD `7939341fd9d98d0f1fa39ce4421318dbc1dac33e`; tree `6bf30ee0d11c8137ec6a77844b1517de50d89edd`; parent `3be566129be44e00e92a07dd9449c957751eeb5d`. Candidate branch `codex/whitepact-m13-absolute-convergence`, [draft PR220](https://github.com/Guruprasath-Annadurai/Whitepact/pull/220). Production `src` subtree `bbd0e5f0b6a7dd02b388ab45d4dc5a7fed9036f1` is unchanged since296ad7ff. Final reports live on documentation-only branch `codex/whitepact-m13-absolute-evidence`. Historical receipts identify their own HEAD and do not substitute for final7939341f evidence.

Verdict: NOT ACCEPTED. Complete accounting and a passing suite are separate gates. No partial/predecessor coverage qualifies the candidate.

## Final exact-head run

[Bounded full matrix39156412888](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39156412888).

Terminal outcome: **FAILURE**, attempt1. All16 shards completed; complete_accounting=true for both interpreters. Independent XML validation confirms7,950 unique case elements per interpreter, matching the selected inventory; no missing/duplicate cases or collection skips.

|Python|Cases|PASS|FAIL|ERROR|SKIP|
|---|---:|---:|---:|---:|---:|
|3.11.17|7950|7849|66|1|34|
|3.12.15|7950|7850|66|0|34|

|Coverage|Required|Python3.11|Python3.12|Verdict|
|---|---:|---:|---:|---|
|Blended|80%|87.8412%|87.9925%|PASS threshold only|
|Statements|90%|90.1271%|90.2488%|PASS threshold only|
|Branches|80%|78.8935%|79.1609%|FAIL|

Each interpreter measures33,678 statements/8,604 branches. Actual covered statements:30,353/30,394; covered branches:6,788/6,811. No threshold rounding or waiver. Failed tests and below-policy branch coverage prevent acceptance even though statements/blended meet thresholds.

|Shard|Cases|3.11 P/F/E/S|Seconds|3.12 P/F/E/S|Seconds|
|---|---:|---|---:|---|---:|
|0|994|988/3/1/2|552.66|989/3/0/2|437.74|
|1|994|991/3/0/0|162.34|991/3/0/0|180.49|
|2|994|975/17/0/2|336.53|975/17/0/2|469.26|
|3|994|984/10/0/0|447.63|984/10/0/0|463.62|
|4|994|984/10/0/0|261.32|984/10/0/0|324.21|
|5|994|989/1/0/4|411.03|989/1/0/4|524.99|
|6|993|963/7/0/23|636.85|963/7/0/23|382.15|
|7|993|975/15/0/3|282.76|975/15/0/3|429.15|

P/F/E/S means passed, failed, errors and skipped. No shard execution hard timeout occurred; the3.11 teardown error remains an individual120s error.

Execution sums: 3091.12s on3.11 and 3211.61s on3.12; these are job execution sums, not wall time. Official run wall time25m07s:2026-10-19 00:25:51–00:50:58 Asia/Kolkata (source API timestamps18:55:51–19:20:58 UTC on October18). All shard selections match inventory SHA256 `682bbb5e85f28a41a1f7ab460a1b914d57a2da6178fb0b9fba0913bd0cb07fca`.

Artifacts: `full-suite-{3.11,3.12}-{0..7}-7939341fd9d98d0f1fa39ce4421318dbc1dac33e` and `full-suite-aggregate-{3.11,3.12}-7939341fd9d98d0f1fa39ce4421318dbc1dac33e` in run39156412888. Aggregates contain real coverage.json/XML and full-suite-summary.json; shards include plans, inventories, JUnit, skips, dependency versions and raw coverage. Downloaded locally to `/private/tmp/m13-7939341f-full-complete`; complete CI log `/private/tmp/m13-7939341f-full.log`.

The corrected wheel/fresh-consumer case PASSes on both interpreters (verified directly in actual final JUnit). Remaining66 failures per interpreter comprise28 root bootstrap,24 migration-head,5 tracking oracle/policy,3 H4,1 protected restore status,1 CPU timing,1 upstream governance-state/error precedence,1 DCO,1 data inventory and1 source-introspection assertion. Actual CPU case durations4.2261s/4.1906s exceed unchanged3s; not labeled flaky.

Additional3.11 ERROR: `tests/test_plan_scaled_route_limits.py::test_scaling_is_per_organization` teardown exceeded120s while asyncio.Runner._cancel_all_tasks awaited pending tasks. The request assertions and application shutdown completed first. The CI artifact does not identify the responsible task, so root cause remains UNRESOLVED. One bounded original-file local check at the same HEAD returned6 PASS in25.73s on macOS/Python3.11.15 with a different host/backend environment; this neither reproduces nor closes the CI/suite-order error. Local log/JUnit `/private/tmp/m13-7939341f-route-limits.{log,xml}`. No timeout is counted as SKIP/PASS.

Final execution skip reasons match the34-category accounting below; zero collection skips. Local optional-consumer and Bash results are separate platform evidence, not substitutions in these totals.

All eight compatible shard plans must identify the same HEAD, inventory hash and interpreter. The combiner rejects missing indexes, duplicate/missing node IDs, mismatched source and incomplete JUnit accounting before coverage combination. It emits actual failed-shard details, execution skips and collection skips. Failed/error/timeout tests never become SKIP/PASS. Per-interpreter coverage remains measurable after failures but never accepted as full-suite success.

## Inventory, dependencies and resource contract

Final 7939341f manifest:7,950 parametrized cases,6,374 distinct pre-parameter node identities,541 files. Marker inventory: asyncio3940, parametrize2351, hypothesis74, usefixtures35, skipif27, one m4_hostile_smoke and one m4_postgres_assault. Marker counts overlap and are not additive. Actual inventory SHA256 `682bbb5e85f28a41a1f7ab460a1b914d57a2da6178fb0b9fba0913bd0cb07fca`; the combiner must verify every shard shares this manifest. First final artifact records Python 3.11.17, exact HEAD/tree/parent above and clean Git status.

Eight disjoint whole-file shards preserve module fixture isolation: weights994×6 and993×2. No xdist/shared-database concurrency. Each job has isolated PostgreSQL16 and Redis7 services, real Docker runtime image, ACL/nftables/iproute2/nginx tools, TypeScript SDK build, root npm dependencies and Chromium. PYTHONPATH includes src:sdk/python:.; wheel qualification installs build and repository-pinned hatchling1.32.0. Existing wave1 framework pins run locally controlled providers, with no paid model call.

Supported Python 3.11/3.12, Ubuntu24.04. Test timeout120s via Linux signal; faulthandler90s; shard hard timeout1500s; job35min. Eight concurrent free public-repository runners maximum; no paid credits or infrastructure. Each shard records dependencies, HEAD/tree/parent, clean Git status, inventory, marker categories, selected node IDs, durations, full JUnit, skip reasons and hidden coverage data. Collection bound180s. Benchmarks and live-provider/operator requirements do not silently become passing tests.

## Timeout diagnosis and corrections

The predecessor 38f3ceb0 run 39100572294 stopped at 33% after90min: incomplete, not accepted. Measured profiling identified frozen time.monotonic in ordinary container-coverage fixtures: deadline loops could never expire, while unknown inspect state was incorrectly expected to prove absence. Editable ordinary clocks now advance; true absence fixtures supply Docker's explicit “No such container” diagnostic; inspect exceptions explicitly deny. Original protected security assertions remain unchanged.

Fresh-process sharding exposed an annotation-only serialization→graph circular import, corrected using TYPE_CHECKING; no serialization algorithm changed. Source import regression cases pass in isolated processes. Further measured setup corrections supply SDK import paths, explicit Chromium, image environment, build and pinned hatchling. The no-isolation SDK wheel/fresh-consumer negative-transport test returned1 PASS in 12.91s after backend installation before the final corrective CI checkpoint.

No Docker error is reclassified as absence; no cleanup timeout, containment invariant, protected negative assertion or coverage policy is weakened.

## Existing coverage policy

Blended coverage minimum80%; pure branch minimum80%; statement minimum90%. Each interpreter combines independently from complete same-source artifacts. No stale XML, hand-authored coverage, mixed-HEAD data or skipped requirement is counted as passing.

Predecessor 3be56612 run 39138088394 completed all16 shards with complete_accounting=true and zero collection skips. Each interpreter:7,950 cases,7,849 PASS,67 FAIL,34 SKIP,0 ERROR. Python 3.11 blended87.8364%, statements90.1182%, branches78.9052%; Python 3.12 blended87.9996%, statements90.2488%, branches79.1957%. Branch coverage fails80%. Longest shard645.19s; aggregate execution sums2974.69s/3357.57s (CPU job seconds, not wall time). These are predecessor observations, not final 7939341f acceptance.

## Skip dispositions

Predecessor 34 execution skips per interpreter:22 missing optional CrewAI/LlamaIndex consumers;3 Terraform CLI absent;2 Bash3.2 unavailable;3 documentation examples requiring a live API key, home-directory write or caller-supplied provider;1 shallow-checkout historical M5 object;1 already-covered async boundary marker;1 ACL/root-unavailable path inapplicable on privileged capable Linux host;1 benchmark not explicitly requested. Final skip inventory must confirm actual reasons. No live key, Terraform/cloud provisioning, package publication or paid service is introduced to erase skips.

CrewAI/LlamaIndex separately use pinned isolated environments and localhost HTTP fixtures; actual final-head macOS results are in customer report. They do not convert Linux skips into passes or qualify Core authorization. Bash3.2, Terraform, external-provider and operator paths remain NOT_EXECUTED unless separately evidenced. The inherited ACL/root skip describes an unavailable refusal path on that host; neighboring stub/native tests are distinct evidence.

Separate final7939341f macOS Bash3.2 qualification:2 PASS in3.05s, `/private/tmp/m13-7939341f-bash32.{log,xml}`. These verify actual shell syntax and immediate missing-backup refusal before any database/network action, not successful database restoration. The two Linux unavailable-Bash3.2 skips remain skips in that host's inventory. No live restore or cutover ran.

## Failed-gate disposition

Full predecessor failures include28 root-bootstrap subjects lacking required genuine A2/session setup or downstream qualification;24 old migration-head assertions;5 immutable tracking-policy/oracle conflicts;3 owner H4 cases;1 protected restore500-vs-disabled503 conflict;1 missing wheel backend (corrected final CI);1 actual CPU-duration failure;1 upstream governance-state/error-precedence case;1 historical DCO range;1 four-table data inventory gap;1 source-introspection revocation assertion. These sum67 for that predecessor. No blanket “outdated test” verdict: unreached downstream assertions remain unqualified, source/behavior contracts require owner disposition, and actual restore defects remain security blockers.

Final failure names/messages remain in per-shard results.xml and aggregate summary; final exact counts/coverage and durations supersede predecessor arithmetic. Original67 do not become PASS through reclassification.

## Diagnostic run ledger

- 39131867768/6318439b: cancelled after reproducible circular import/collection mismatch; diagnostic only.
- 39132839624/de9c2d1e: all3.11 shards attempted, one lost JUnit at frozen-clock cleanup;3.12 superseded. Partial totals not full acceptance.
- 39134982899/bc29df24: explicitly cancelled after confirmed unauthenticated restore mutation required production-source containment.
- 39136062599/296ad7ff: allowed to finish for full diagnostics; ordinary fixture/environment defects drove corrections. Earlier informal3.11 subtotal was overstated by10 failures; actual eight-shard subtotal73 FAIL, not83.
- 39137317495/c46dffb5: cancelled specifically after missing build module/image environment were independently identified; not accepted.
- 39138088394/3be56612: completed full accounting,67 failures and below-policy branch coverage; missing no-isolation hatchling backend independently corrected afterward.
- 39156412888/7939341f: final run; no predecessor result substitutes.

No CI quota denial occurred. A skipped/missing dependency is not attributed to invented usage limits. Full-suite, coverage, DCO and protected gate failures remain release blockers.
