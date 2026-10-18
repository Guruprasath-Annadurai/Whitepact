# M13 full suite and coverage acceptance

Status: IN_PROGRESS / NOT ACCEPTED.

Predecessor38f3ceb0 full run39100572294 timed out at90 minutes on both interpreters. Last progress33%; no final JUnit. Retained early coverage.json is not final coverage.

Measured diagnostic: /private/tmp/m13-convergence-stall-profile.log reaches test_final_coverage_batch12.py::test_remove_containers_tolerates_rm_errors and stops. It fixes time.monotonic at1000 while _remove_containers waits for a future deadline. Inspection never proves absence. The editable ordinary coverage test now advances deterministic time and explicitly requires fail-closed RuntimeError; no production cleanup guard was weakened. The original protected negative reproducers are unchanged. Focused corrected test passed.

Corrected stalled region:130 PASS,27 warnings in130.96sec (batch12+13); /private/tmp/m13-convergence-profile-green.log. Production cleanup unchanged. The former unbounded diagnostic was stopped after identifying its frozen-clock loop.

Local collection before importing owner suites:7775 baseline cases;7781 after six new counterexamples. These are environment-specific counts, not final CI inventory. Actual final inventory must come from each committed-head job.

New qualification runner collects all supported tests with marker inventory, balances whole files by case count into8 disjoint shards, preserves module fixture isolation, uses isolated CI services per job, emits exact source/tree, full inventory, selected inventory, timings, JUnit, skips and coverage data. Test timeout120sec (failure), shard execution timeout1500sec (failure), job timeout35min. No xdist shared-state database concurrency.

Aggregate requires8 distinct indexes, identical HEAD and manifest hash, no duplicate/missing selected node, and exact completed JUnit count before combining coverage. Each interpreter combines separately. Existing blended80%, pure branch80%, statement90% gates remain. Any failed/error/timeout shard or skipped test prevents aggregate acceptance; skip reasons require explicit disposition. Missing or stale coverage never qualifies.

Current CI run/artifact references and actual pass/fail/skip/duration/coverage totals: NOT YET AVAILABLE for this integrated candidate. No partial or previous-head result is reported as complete acceptance.

First bounded run39131867768 on6318439b was explicitly cancelled after a new deterministic fresh-process circular import prevented shard2 collection (expected992, selected971, pytest exit2). serialization imported graph.snapshot, graph.__init__ imported graph, which imported canonical_sha256 before serialization defined it. The GraphSnapshot import is annotation-only and now TYPE_CHECKING-only; serialization algorithms and authority enforcement are unchanged. New independent-process import tests accompany the correction. This cancelled run is diagnostic evidence, not full-suite acceptance. A corrective final-head run is required.
