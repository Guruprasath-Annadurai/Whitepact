# WhitePact M13 Windows-only P0 continuation

28 October 2026 — Asia/Calcutta. M13 OPEN. GLOBAL PRODUCTION NO-GO. M14 NOT AUTHORIZED.

Base: PR237 `cdd4e669f9b357d7c3a73927bec837c2b3feb7b7`, tree `e354d63d5cd490ead0e33e0f3b03167d7859d54f`.
New worktree: `work/Whitepact-p0`; branch `codex/m13-windows-isolation-p0`.

## Preserved contract

1. Persist pre-execution evidence. If persistence fails: no approval consumption, probe or nonce admission.
2. Atomically consume exact approved action. No reset to APPROVED.
3. Initialize canonical backend and probe runtime prerequisites. Only this executor boundary emits the proven pre-admission exception.
4. Admit through existing nonce/epoch repository and revalidate permit.
5. Dispatch. Any isolation/OSError after admission remains uncertain, even if named 'unavailable'.

|Failure point|Approval|Nonce|Durable outcome|Permitted response|
|---|---|---|---|---|
|Evidence write fails|APPROVED|Unspent|No outcome without evidence|Refuse|
|Initialization/preflight refuses|CONSUMED|Unspent|BLOCKED if write succeeds|503 sanitized; no replay|
|Nonce admission fails|CONSUMED|Unknown if DB acknowledgement lost|Conservative UNKNOWN|Reconcile|
|Backend fails after admission|CONSUMED|Spent|UNKNOWN|503 sanitized; reconcile|
|Outcome write fails|CONSUMED|Depends on admission|Missing outcome remains unresolved|Never reset/replay|
|Concurrent same approval|One consumption winner|At most one dispatch path|Per winning attempt|Loser refused|

Preflight is transient, not a reservation or exactly-once side-effect guarantee. An unspent nonce never authorizes reuse of a consumed approval. New human approval/replacement or operator reconciliation requires existing authority and must not reuse uncertain side effects automatically. No new automatic reconciliation authority implemented.

Independent read-only reviewer found two production issues during iteration: eager constructor refusal bypassed accounting; broad handler mislabeled policy denials. Both corrected and regression-covered. Follow-up static review found PG16 fixture tenant FK and string-version issues; corrected with protected tenant setup/string consent version. Reviewer ran no tests and did not grant final acceptance. Cancellation/kill may leave MISSING_OUTCOME; existing durable evidence/consumption must remain for reconciliation. Full crash recovery qualification is still mandatory.

## Provenance boundary

This is a new Codex reconstruction, not recovered Antigravity source. Original repair commits remain unavailable. Publication and final independent acceptance are separate gates.

## CTO decision — strict at-most-once Option A

The 28 October directive adopts strict single-use approval consumption as the interim contract. No two-phase lease, approval reset or automatic retry is implemented. A proven blocked attempt requires a fresh authorized request; uncertain execution requires reconciliation before further authorization.

If BLOCKED cannot be durably recorded, callers receive the conservative UNKNOWN/reconciliation-required error. The last committed approval, evidence and nonce remain authoritative. Cancellation attempts UNKNOWN persistence and propagates; hard kill, repeated cancellation and database failure can still leave a missing outcome that requires reconciliation.

The new named twenty-scenario suite also adds a cancellation regression. It distinguishes real database/worker tests from simulated Docker failure boundaries and the native-container test. Local Windows skips native containment explicitly. Historical assertions and mandatory coverage configuration remain unchanged. PostgreSQL 16 and native Linux acceptance remain required.
