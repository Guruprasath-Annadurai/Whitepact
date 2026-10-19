# M13 Final Convergence: independent source review

Current candidate:bb6e263fc271a07f58484ce1fd1445cc201b24b0;
tree93f36747cd00610850c8cf0ace13de107b145da5;
parent2bde48d4abe20312dd6408cf62366d68ca69746e.
https://github.com/Guruprasath-Annadurai/Whitepact/pull/223
Exact-head full/native/customer/security matrices are pending extraction.

Further boundary review reproduced HTTP mutation200 instead of503 after a
post-startup durable pending marker (1FAIL2.66s), and stale read-only READY on
SQLite/PostgreSQL (2FAIL14.04s). Corrected HTTP/status4PASS25.54s across both
databases; modified two HTTP source files mypyPASS. Customer middleware now
queries live DB before non-recovery paths, and operator status reports current
DB admission. Original narrow recovery allowlist and disabled public restore
remain unchanged. Prior2bde broad jobs were superseded/canceled; canceled is not
a completed matrix or a quota denial.

Status: IN PROGRESS. M13 OPEN. GLOBAL PRODUCTION NO-GO.

## Verified source provenance

Fetched canonical remote before creating the integration worktree. PR221 remains
`codex/whitepact-m13-ironclad` at `ccf4e8cc80f1de52a0a9b445298055ac581f53e1`,
tree `c7bef348b9dcea2e55a86d4b01f357fb1498ecd2`, parent
`47fc55a1591890f18c06333b4f187d091535719d`.
PR222 is `antigravity/whitepact-m13-recovery-zero` at
`e7e24dee0c828bbbe8c08db6e519aedf3cc0a0d2`, tree
`2acb1cdc9e397e2ec35209b45b6d87ce33ac8f52`, parent
`314574faa9395ad23cd260e1c4b01f863c40c876`.
Merge base is `7939341fd9d98d0f1fa39ce4421318dbc1dac33e`.
Dedicated candidate branch starts from verified IRONCLAD. Original branches and
PR220/221/222 are preserved. No wholesale merge has been performed.

Owner source: https://github.com/Guruprasath-Annadurai/Whitepact/pull/222
Baseline source: https://github.com/Guruprasath-Annadurai/Whitepact/pull/221

## Independent counterexamples before integration

Explicit owner-source test script:
`scripts/engineering/reproducers/test_m13_final_owner_review.py`.
Run with owner checkout src first on PYTHONPATH. Docker subprocess responses are
controlled; no foreign real container is destroyed and no customer authority is seeded.

Exact owner e7e24dee: **4 FAIL in4.14s**. Receipt:
`/private/tmp/m13-final-owner-review-red-v2.xml`.

1. `verify_authoritative_container_containment` invokes `docker rm -f` using an
   arbitrary supplied name before any tenant/execution/CID ownership proof.
   A stale or foreign name can target a different tenant or an ABA replacement.
2. `corrupted.json` unreadable tracking is ignored for a specific tenant,
   incorrectly returning an empty unresolved list.
3. `unattributed.json` has the same fail-open outcome. Filename attribution is not
   proof that unknown execution authority belongs to another tenant.
4. After `check_database_authority` caches a clean startup, a real SQLite
   CONTAINMENT_PENDING record is committed. Synchronous `assert_traffic_admitted`
   still permits traffic. Production consumers use this synchronous guard;
   startup inspection does not prove current database authority.

The earlier three-case run independently failed3/3 in3.00s; both logs are retained.
The four-case script supersedes it without editing original historical reproducers.

## Initial hunk decisions

- Reject name-only destructive recovery verification and its automatic retry callers.
- Reject unknown/unreadable tracking suppression; preserve IRONCLAD uncertainty.
- Preserve private receipts, owned spawn/registration/cancellation, bounded drainage,
  exact cancellation counts and unknown-create fail-closed behavior.
- Review selective PostgreSQL FK-safe reconciliation, canonical governance floor,
  forensic revocation and durable Store B logic independently before acceptance.
- Startup-only DB checks require live admission integration; no READY acceptance
  inferred from owner focused green CI.
- Public restore stays disabled503. Existing original tests remain immutable.

## Original test-change review

Owner adds singleton resets and temporary tracking-directory isolation; these may
be legitimate fixture isolation, but original replay remains required. Owner also
changes a termination mock to returnTrue, changing its containment attestation.
Owner broadens QUARANTINED to DISABLED-or-QUARANTINED. Runtime GovernanceStatus
permits ACTIVE/SUSPENDED/DISABLED; schema and enforcement must be proven on real
PostgreSQL. The old assertion is preserved; no founder disposition is presumed.

Initial combined replay failed collection with ImportPathMismatchError because
two worktrees exported tests.conftest. This is ERROR, not product FAIL/PASS.
Replay was restarted with one test root and explicit owner-source imports;
results remain pending at this checkpoint. Owner-focused new cases run separately.

## Independent execution and first selective integration

Owner-focused new tests on exact e7e24dee: **20 PASS in223.40s**,
`/private/tmp/m13-final-owner-focused.xml`. Unchanged historical replay on that
same source: **20 PASS/3 FAIL in66.86s**, receipt
`/private/tmp/m13-final-owner-original-replay-v2.xml`. Failing originals are H4
test07 (mock gives no true termination attestation), H4 test11 (original
QUARANTINED assertion), and PostgreSQL tombstone/FK test (earlier unresolved
execution remains). These original gates are not relabeled by owner counterparts.

First selective source includes reviewed database/FK/Store B reconciliation and
startup error fencing; owner in_flight name-only deletion and unreadable-record
suppression are rejected. Private receipt/cancellation code stays IRONCLAD, with
immutable-CID metadata and creation labels added. Recovery removal requires exact
CID plus matching daemon-provided tenant/execution labels, never name-only rm.
Legacy/name-only records remain unresolved; loss of a tracking file does not
clear memory uncertainty. Remote registration generation is preserved for
compare-and-delete cleanup, preventing replacement-registration deletion.

Consequential guards now await current database authority, rather than using a
startup cache. Bound-database synchronous calls deny and require the async guard.
Startup query exceptions also persist FAILED rather than only logging a warning.
Store B remains authoritative; no prototype/default identity relaxation.

Additional inherited detached-entry defect independently RED1/1 in2.20s:
task=None and callback=None were treated as confirmed containment. Corrected
implementation retains UNRESOLVED without positive termination proof.

Integrated focused contracts: **45 PASS in12.48s**, including all four unchanged
owner-review assertions, receipt/cancellation scope, live-marker checks and
eight immutable-identity/mismatched-identity/error checks. Receipt
`/private/tmp/m13-final-integrated-contracts-v2.xml`. This is local/component
evidence, not native Linux or final candidate CI. Mypy all427 source files PASS.

An earlier integrated slice recorded24 PASS/7 FAIL138.95s on original recovery
plus A2/admission tests with retained shared tracking. Those failures remain
preserved in `/private/tmp/m13-final-integrated-first.xml`; no tracking records
were deleted or original expectations edited to hide them. Fresh PostgreSQL
live-marker and full/native matrices remain required on the committed successor.
