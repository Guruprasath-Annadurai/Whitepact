# IRONCLAD runtime specification

Final qualification update (2026-10-19): frozen implementation HEAD `ccf4e8cc80f1de52a0a9b445298055ac581f53e1`, tree `c7bef348b9dcea2e55a86d4b01f357fb1498ecd2`, parent `47fc55a1591890f18c06333b4f187d091535719d`. Draft PR #221 targets `codex/whitepact-m13-absolute-convergence`. Evidence-only branch adds tests/reports; implementation equivalence is checked independently. The current results below supersede historical pending statements retained later in this audit trail. M13 OPEN. GLOBAL PRODUCTION NO-GO.

## Current exact-source evidence

Exact-source native targeted run39243112392: Python3.12 **131 PASS**; Python3.11 **129 PASS/2 FAIL**, no native skips. Two original same-organization lifecycle expectations conflict with persisted UNRESOLVED after an interrupted create without a trusted receipt. They remain FAIL; do not erase uncertainty. Reference cohort inherits that state on3.11 (984 PASS/8 FAIL/2 SKIP), versus3.12 (989 PASS/3 FAIL/2 SKIP). Evidence-only commit `3e9d6b780672b568b3130649e0ec0e09975c91e1`, run [39246319117](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39246319117), independently passes **4 cases each** with source unchanged: two actual Docker known-ACK/lost-receipt tenant probes plus two controlled plugin-error callback contracts. Neither original native tests nor original plugin reproducer is altered. Runtime Review39243120593 remains FAIL:53 PASS/2 FAIL each; original plugin callback reproducer mocks the delegated cleanup method, so its assertion no longer observes actual shared inspection. That original gate requires maintainer disposition and is not relabeled PASS. Actual PostgreSQL restore1 PASS/2 FAIL each (StoreB floor and restrictive FK). Antigravity recovery-zero `8f1717c1bf1b5bbfe6fb0afc24f4bdc8ba73d9e1` was fetched only, not integrated or accepted. Public restore remains503.

## Preserved invariants

Exact database identifiers must not NFC-alias. Registration cannot overwrite existing uncertain authority. UUID compare/delete cleanup and bounded shared lock preserve ownership. Epoch fencing uses canonical governance scope. Daemon/plugin/inspect errors do not prove absence; unreadable/corrupt tracking remains unresolved. Dead worker PID does not prove dead container. This checkpoint changes no runtime containment source.

## Original five immutable failures

| Exact test | Observation and disposition |
|---|---|
| test_h1_collision_invariance.py::test_07_slashes_and_traversal_attempts | Counts2 entries rather than1: trackingJSON and required.registry.lock. Preserve assertion; specification disposition required; JSON identity safety qualified separately |
| same::test_10_unicode_normalization_nfc | Expects aliased NFC-equivalent IDs; exact DB identifiers deliberately produce distinct paths. Do not merge authorities |
| test_inflight_liveness_adversarial.py::test_kill_esrch_unlinks_dead_worker_tracking | Expects unlink after workerESRCH; container state remains unknown, retention required |
| test_h1_reproducers.py::test_reproduce_distributed_tracking_prefix_ambiguity | Corrupt legacy record triggers unresolved admission; unknown owner cannot safely be assumed foreign |
| test_h1_tenant_isolation_adversarial.py::test_10_tenant_prefix_ambiguity_worker_tracking | Empty tracking file triggers unresolved admission; same unknown-owner invariant |

These are FAIL gates requiring formal disposition, not passing regressions. Unknown legacy authority blocking unrelated tenants is an explicit availability tradeoff requiring operator policy, not grounds to erase records. Readable attributed foreign-tenant records must continue to be filtered.

Original 16 tracking cases and native Linux/cancellation matrices are historical793 evidence. New-head repetitions remain pending. No H4 code/tests modified. Antigravity handoff remains canonical StoreB epoch reconciliation, restrictive PostgreSQL FK deletion order and qualified operator readiness/fencing. Public restore aliases remain503; protected expected500 test remains FAIL and requires documented acceptance disposition only.

## New independently reproduced containment defects and corrections

At committed d9ddf44a, a deterministic negative test caused a forged workspace .container.cid value to become a foreign-container removal target. This was an attempted target in a controlled test, not deletion of another customer's real container. Preserved container RED JUnit: /private/tmp/m13-ironclad-container-ownership-red.xml.

Creation receipts now live in a fresh, unmounted host-private0700 directory. Descriptor checks require O_NOFOLLOW/O_NONBLOCK, an owned regular single-link file, exact64-byte lowercase ASCII hex, and a bounded read. Only the trusted Docker client can supply this receipt under the stated same-UID/daemon trust assumptions. Verified acknowledgments are cached for same-worker cleanup retries; a process restart does not infer ownership from dead PID.

Callback and normal cleanup target exact acknowledged ID plus generated invocation name, preserve daemon/inspect uncertainty, and complete under owned cancellation handling. Interrupted creation without an acknowledgment remains UNRESOLVED even after the existing bounded absence-observation window: a finite window cannot exclude later daemon creation. This intentional availability cost needs qualified operator disposition, never silent record deletion.

Independent review then reproduced cancellation during spawn handoff and during registry-lock admission: both could leave an untracked client/container. Two unchanged barrier reproducers were RED in2.28s on the intermediate container source blob461b0dc71f4c8b75eb9ef6f612c8c68ba493de8b. Creation and registration handoffs now complete under ownership before cancellation propagates; registration transfers its task ownership synchronously to the executor. Denial adds no cancellation to an uncanceled caller. Bounded PIPE draining/reaping prevents Process.wait from hanging on buffered output; drainage uncertainty remains unresolved.

Final local focused matrix: **48 PASS,8 SKIP in4.89s**, /private/tmp/m13-ironclad-container-final-local.xml. Includes unchanged cancellation reproducers, early lifecycle barriers, exact cancel counts, private receipt validation and ordinary CID cleanup fixture. Eight native-host cases remain SKIP locally and require actual Linux CI. A first combined run had5FAIL/31PASS and was preserved; after fixing cancellation ownership at the cleanup call boundary and using a fresh isolated temporary registry, its36 cases passed5.17s. Existing shared tracking records were preserved.

Only one ordinary non-H4 branch-campaign fixture was updated to model Docker acknowledging a valid64-hex receipt at --cidfile. It no longer injects a malformed workload-controlled CID. Its cleanup assertion remains. Protected original reproducers and H4 recovery-specific functions remain unchanged. Native Linux, installed CLI source ordering and timing are pending successor CI.

Artifact correction: an agent overwrote the initial local transfer RED/GREEN XML paths. Original transfer raw logs remain intact, and exact d9ddf44a CI authority XML independently preserves their Linux counterparts. Container receipts now use distinct names; the overwritten transfer XML is not claimed as retained evidence.
