# M13 FORTRESS independent acceptance

Tested source HEAD `7939341fd9d98d0f1fa39ce4421318dbc1dac33e`; tree `6bf30ee0d11c8137ec6a77844b1517de50d89edd`; parent `3be566129be44e00e92a07dd9449c957751eeb5d`. Candidate branch `codex/whitepact-m13-absolute-convergence`, [draft PR220](https://github.com/Guruprasath-Annadurai/Whitepact/pull/220). Production `src` subtree `bbd0e5f0b6a7dd02b388ab45d4dc5a7fed9036f1` is unchanged since296ad7ff. Final reports live on documentation-only branch `codex/whitepact-m13-absolute-evidence`. Historical receipts identify their own HEAD and do not substitute for final7939341f evidence.

Verdict: selective integration accepted for review; overall security qualification BLOCKED. M13 OPEN. GLOBAL PRODUCTION NO-GO.

## Verified provenance

Original APEX PR216 remains OPEN/DRAFT at 38f3ceb0a6f8be85782997822b80f83d10c8823d, treec10eac22c582ee4248fbfdb9bafe51ec3bc9cabd, parent42bd4889a2519054bfb6f54105a24268d77d7b0e. Original FORTRESS PR219 remains OPEN/DRAFT atf50b0f750fb6e12239f00ba3772ef671167a50ea, treea62d91ea347d89e51cd7819ed2c107bffd3d9c4a, parent7b64ba4ee69dca4ab03ddf6072bd0ee83685d623. Merge base99caa21b50821910fc42e71355c3af5b5ba3ae50. Both originals rechecked unchanged on 2026-10-18 and preserved. Separate convergence worktree; no wholesale merge.

| Owner change | Decision | Independent finding |
|---|---|---|
| Domain-separated filename digest | ACCEPT WITH CORRECTION | Preserve exact database identity strings; NFC-equivalent distinct IDs must not alias. SHA256 has practical collision resistance, not mathematical injectivity. |
| Existing-file replacement | REJECT; corrected | Atomic hard-link no-replace publication preserves existing/corrupt authority. |
| Legacy unknown ownership | REJECT; corrected | Unknown records block actual tenant admission; do not silently disappear from tenant scans. |
| Registration cleanup | ACCEPT WITH CORRECTION | UUID-specific ownership and bounded shared POSIX lock prevent duplicate callback loss and compare/unlink ABA deletion. |
| Cross-scope runtime reconciliation | CORRECTED | Only canonical governance scope fences runtime; no insertion-order collapse across unrelated scopes. |
| MCP SSE tenant/key binding | ACCEPT narrow checks | Missing tenant/key contexts fail closed. Broad transport regressions remain distinct from complete live reconnect/lifecycle certification. |
| H4 backup implementation | REJECT/BLOCKED | Wrong epoch namespace, invalid PostgreSQL quarantine status, restrictive FK ordering, arbitrary epoch constants and incomplete Store B capture. |
| Original nine test files | PRESERVED unchanged | Evidence includes conflicts/failures; copied owner PASS is not independent acceptance. |
| Owner workflow/reports/uv.lock | NOT IMPORTED | Reviewed as evidence assertions; no unneeded lockfile or wholesale CI import. |

Six unchanged new counterexamples against exact owner f50b0f7:6 FAIL, then6 PASS after correction. Follow-ups independently reproduced mixed-scope fencing (2 RED), legacy-owner cleanup (RED) and barrier-controlled cleanup/republication (RED). Corrected tracking scope has16 tests. These initial local receipts precede final HEAD; final runtime/full-suite runs are authoritative.

## Restore handoff to Antigravity/security owner

P1 service blockers: Store B floor7 with restored canonical governance epoch2 returns RECONCILED while canonical epoch remains2; actual approval→runtime-request FK graph prevents candidate reconciliation. Against owner f50, the same real PostgreSQL case fails earlier because QUARANTINED violates chk_org_governance_status. SQLite H4 fixtures do not establish schema compatibility. Arbitrary max(epoch+1000,999999) cannot prove a universal monotonic fence; ordinary revocation capture into Store B was not established.

Required acceptance: verified operator authority; canonical monotonic Store B high-water fencing; concurrent restore/revocation; valid schema quarantine; transactional FK-safe reconciliation with approved root/consent/evidence retention; actual restore-triggered runtime containment. Do not invent legal retention or delete evidence to pass tests. A committed handoff is provided; no external message was sent.

A separate P0 exposure was independently reproduced atbc29: both public restore aliases returned200 and reopened admission without authentication with auth enabled, using real HTTP and fresh migrated PostgreSQL. The unchanged new assertions returned2 RED. Both aliases now unconditionally deny503 RESTORE_SECURITY_QUALIFICATION_REQUIRED without service call or readiness mutation. The same assertions returned2 GREEN before commit and pass in dedicated committed-head qualification when recorded. This contains the HTTP mutation; it does not qualify H4 or operator recovery.

## Minimal independent reproduction commands

From the convergence checkout, using the verified detached owner source atf50b0f7 and the same isolated PostgreSQL helper (never production data):

```sh
PYTHONPATH=/private/tmp/whitepact-fortress-independent/src:. python -m pytest tests/test_m13_convergence_tracking.py -o pythonpath='' -k 'distinct_database_identifiers or duplicate_authority or corrupted_record or unreadable_legacy or concurrent_registration or symlink_tracking'
PYTHONPATH=/private/tmp/whitepact-fortress-independent/src:. python -m pytest scripts/engineering/reproducers/test_m13_fortress_restore_independent.py::test_store_b_floor_fences_canonical_governance_epoch scripts/engineering/reproducers/test_m13_fortress_restore_independent.py::test_tombstone_reconciliation_handles_real_approval_request_fk -o pythonpath=''
```

The first selection is the same six original independent assertions (historical owner receipt6 RED). The second selects only the two owner PostgreSQL assertions actually run historically (2 RED); it does not misattribute the subsequently added canonical-runtime-scope case to that owner receipt. Clearing pytest's pythonpath override is necessary so tests exercise owner source, not current src. Final candidate versions run under its ordinary src path in Runtime Review.

Public restore counterexample: run tests/test_m13_convergence_restore_http.py against a separate bc29df24 source worktree with the same pythonpath override. Both aliases returned200 and cleared quarantine (2 RED); current source unconditionally denies503 and preserves quarantine (2 GREEN, then committed-head dedicated qualification). Real app/HTTP/PG are used; no authorization or reconciliation service mock manufactures this boundary.

## Preserved owner test blobs

All nine final candidate blobs equal exact owner f50b0f7 blobs; failures are retained as evidence.

|Path|Unchanged Git blob|
|---|---|
|tests/test_h1_reproducers.py|`c63bc117bff9e2514289d4a1d0f985098e719683`|
|tests/test_h1_collision_invariance.py|`e8e948ee1b18e8f4fcdae2f9afc6f6087e881d80`|
|tests/test_h1_mcp_sse_transport_security.py|`c81c2cce4243762fbda9bc3a919d6b373449c9d7`|
|tests/test_h1_tenant_isolation_adversarial.py|`5ce99c6be390c3e0d0dec8b3b4869b05f1d40887`|
|tests/test_h2_linux_containment_adversarial.py|`082f4d0afa3a392790c2ee4446cc1921199f75f9`|
|tests/test_h3_audit_evidence_adversarial.py|`a798c8231658ae110909436899ad544f1a9338d2`|
|tests/test_h4_backup_recovery_adversarial.py|`ccd8d2889df87b97b052c2b8f814521e53607fef`|
|tests/test_h5_developer_onboarding_acceptance.py|`86b9e7b8c6f85c1c01bdf296ba010882b1b3cdcb`|
|tests/bench/test_h6_performance_concurrency_bench.py|`1e9cba69123e993fe64d3c4cc2ce56f3fd666d6a`|

## Evidence boundaries

Final 7939341f Independent Integration39156415461 FAILURE. Full MCP transport/session519 PASS per interpreter (111.47s/162.59s), with9/7 warnings retained; mandatory downgrade restriction/rollback4 PASS per interpreter (25.45s/32.74s); WebAuthn origin/identity83 PASS (20.31s/29.53s). Actual native-container scope 15 PASS in 113.76s. Original assertions10 FAIL/26 PASS, revocation/egress1 FAIL/208 PASS, selected root-boundary3 FAIL/3 PASS/3 deselected per interpreter. Targeted deselection is not full inventory coverage. Whole inherited Ruff141 errors remains failed. No scoped success waives these failed mandatory gates. Final full matrix separately inventories all tests.

H2 subprocess/flag and injected failure tests are not native Docker proof. H3 local hash-chain/signed file witnesses are not independently operated immutable external anchoring. H4 SQLite success is not PostgreSQL restore proof. H5 constructor/mock transport tests are not complete customer authority. H6 in-process microbenchmarks are not API latency/SLA/disaster-recovery certification. Actual Linux, PostgreSQL, MCP and final-head counts are in the runtime and final reports.

Original owner assertion conflicts remain visible: NFC aliasing; ignoring ambiguous legacy ownership; directory entry count includes required .registry.lock. No original assertion is rewritten or reported PASS. Unsupported network filesystems, noncooperating writers, mixed incompatible binaries and safe automated legacy reconciliation remain UNQUALIFIED.
