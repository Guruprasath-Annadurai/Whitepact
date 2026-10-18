# M13 FORTRESS independent acceptance

Status: PARTIAL; production NO-GO. Owner source f50b0f750fb6e12239f00ba3772ef671167a50ea, tree a62d91ea347d89e51cd7819ed2c107bffd3d9c4a, parent7b64ba4ee69dca4ab03ddf6072bd0ee83685d623. APEX baseline38f3ceb0a6f8be85782997822b80f83d10c8823d. Merge base99caa21b50821910fc42e71355c3af5b5ba3ae50. Both remote heads verified unchanged on2026-10-18. Existing checkouts preserved; no wholesale merge.

|Change|Decision|Evidence / limit|
|---|---|---|
|Digest filename framing|ACCEPT WITH CORRECTION|Exact database strings, no NFC folding; practical SHA-256 collision resistance, not mathematical injectivity|
|Registration publication|REJECT original; corrected|Original replaces existing authority/corrupt records; corrected atomic hard-link no-replace publication|
|Legacy unknown ownership|REJECT original; corrected|Original non-JSON legacy file permits tenant admission; corrected unresolved admission|
|MCP missing tenant/key checks|ACCEPT provisionally|Two narrowly selected conditions; original HTTP tests imported unchanged, actual SSE stream lifecycle still needs qualification|
|Backup H4 source|BLOCKED; not imported|Wrong epoch scope and PostgreSQL FK order; independent restore evidence missing|
|Owner H1–H6 tests|Preserved unchanged|Imported as regression evidence, not acceptance assertions|
|Owner workflow|NOT IMPORTED|Linux host does not turn mocked Docker cases into actual container proof|
|Owner reports|Historical only|No claims copied as independent qualification|
|uv.lock|NOT IMPORTED|No accepted dependency change requires it|

Six new negative tests independently returned6 FAIL against exact owner source in /private/tmp/m13-fortress-tracking-red.log. The same six returned6 PASS after correction. Follow-up review found registry-level duplicate callback loss and partial JSON acceptance; separate tests and corrections were added. Final integrated validation is pending.

Imported original owner tests additionally introduce50 Ruff findings (41F401,3F841,5B017,1I001). They are preserved as original owner evidence rather than silently rewritten. Whole-tree compliance therefore includes these findings in addition to the inherited baseline; no clean whole-tree claim is made.

## Antigravity handoff: backup blockers

P1/high-confidence source defects on exact f50b0f7:
- backup_defense.py writes scope tenant_global; canonical RevocationEpochRepository defaults to governance. H4 test03 repeats the disconnected scope.
- Approval deletion precedes governance_execution_authorizations, while runtime requests/authorizations and attempts have restrictive foreign keys. A populated PostgreSQL graph can roll back reconciliation.
- max(epoch+1000,999999) is not a universal fencing proof. Store B ordinary revocation capture is not established; production record_state callers located in deletion orchestration.
- Original H4 fixture is SQLite. Manual registry calls in tests07/15 do not prove restore-triggered containment.

Required owner acceptance: real PostgreSQL linked approval→request→authorization→attempt restore; current canonical governance epoch against authenticated Store B high-water state; concurrent revocation/restore monotonicity; actual restore-triggered runtime fencing. No arbitrary constant or alternate epoch namespace qualifies. Preserve roots/consent/evidence pending approved retention policy; SOC2/GDPR references alone do not establish indefinite retention.

This handoff is committed for review; no external message was sent.

## Real PostgreSQL owner reproduction

scripts/engineering/reproducers/test_m13_fortress_restore_independent.py was run unchanged against exact FORTRESS source via PYTHONPATH=/private/tmp/whitepact-fortress-independent/src:. with real fresh PostgreSQL databases migrated to0065. Result:2 FAIL in24.69sec; /private/tmp/m13-fortress-restore-postgres-red.log.

1. ACTIVE Store B floor7 after restored canonical governance epoch2: reconciliation claims RECONCILED, canonical repository still returns2. This directly confirms the wrong-namespace finding. It does not claim an authenticated stale-grant exploit was executed.
2. Tombstoned tenant with a real approval→runtime-request FK: reconciliation aborts earlier than the suspected deletion-order fault. PostgreSQL rejects governance_status QUARANTINED under chk_org_governance_status. This is a third P1/high-confidence compatibility defect; FAILED restore is fail-closed, not successful recovery. The FK-order issue remains source-proven but not reached in this restore reproduction. No schema constraint was removed to manufacture a passing restore.

Expected: valid canonical quarantine with readiness denied until authoritative reconciliation succeeds; correct canonical fencing and legitimate FK/retention disposition. Actual: stale canonical epoch and unsupported status. H4 source remains rejected pending independent owner correction. Fixture rows test restore/schema behavior only; they are not customer-issued authority or a customer journey receipt.

## H2–H6 evidence boundaries

All six owner reports and corrective report reviewed as assertions to verify, not independent receipts. H2 includes subprocess behavior, Docker flag assertions and injected daemon/permission faults; execution on an Ubuntu runner alone does not prove actual containers, kernel resource limits or teardown. Separate actual-container native suites are required. H3 validates local chain/tamper and file-backed signed witness logic; it does not establish independently operated immutable external anchoring or legal retention. H4 SQLite results cannot qualify migrated PostgreSQL recovery, as the independent RED demonstrated. H5 constructor/schema/redaction and mocked HTTP tests are distinct from live MCP session/reconnect and complete developer workflow acceptance. H6 in-process evaluation/concurrency microbenchmarks are not end-to-end authenticated API latency, deployment SLAs, universal memory-leak proof or disaster-recovery certification. Owner numerical latency claims are not adopted as production guarantees.

Final independent runtime review identified two additional reproducible gaps: reconciliation collapses different epoch scopes into one tenant entry (2 RED insertion-order cases), and cleanup can delete another registration's legacy record or a newly republished owner (separate RED cases). Corrections select canonical governance scope, require per-registration UUID on every production cleanup call, and share bounded exclusive POSIX locking across publication and compare/unlink. Barrier-controlled cleanup/republication now passes. All16 independent tracking cases passed locally in6.87sec before final source freeze. Scope: cooperating POSIX workers, trusted local filesystem and stable lock inode; noncooperating writers/network filesystem semantics are not qualified.

Known unresolved admission tradeoff: uninterpretable legacy records remain globally uncertain. The owner prefix-ambiguity test expects them ignored; the current directive requires fail-closed actual admission. Its original assertion is preserved and reported failing. Trusted directory ownership narrows attacker-controlled poisoning, but automated safe reconciliation and availability recovery are not independently qualified. Do not claim this policy fully solves global denial-of-service resilience.
