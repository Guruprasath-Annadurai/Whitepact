# Stage 19–25 handoff for Codex

Branch: `cursor/m13-stage19-runtime-099e`, based on candidate `a5a2fbfcfd17edb3459830ed0eff84003dfec42e` (tree `58756fd88cacf26163cd312c844959c62370edc7`).

Do not rebuild the isolation backend. Use `DockerContainerBackend.execute` only with the enterprise PostgreSQL engine configured and `WHITEPACT_ALLOW_UNISOLATED_EXECUTION` unset. The container path already requires an ACTIVE organization, a current authorization id, a 64-hex action digest, and a timezone-aware expiry. Those checks stayed in place.

## Dependency matrix

| Item | State |
| --- | --- |
| Schema `0067` and containment journal | Satisfied on PostgreSQL 16 in this test |
| POSIX ACL grant for UID 65534 | Satisfied when `setfacl` works. Fail closed otherwise |
| Docker daemon, non-root user, no network, dropped capabilities | Satisfied on this Linux host for one TEST_ONLY run |
| Protected tenant creation | Satisfied only through the existing controller fixture |
| Human approval consumption, nonce, BLOCKED versus UNKNOWN | Already covered by `tests/test_m13_execution_isolation_recovery.py`. Not redesigned |
| Stage 17 approved identity provider | Missing. Customer journey must stay blocked |
| Canonical stages 20–25 after a real execution | Not claimed. No 25/25 result |
| Production host certificate | Not granted. `production_certified` is false |
| PR #239 workflow | Untouched |

## How to attach a later provider-backed path

1. Keep the Stage 17 gate. Do not mark identity verified from this fixture.
2. After a real provider approval exists, create the tenant through the protected controller.
3. Bind the approved action digest and expiry the customer reviewed.
4. Call the existing execute route (`/api/governance/approvals/{id}/execute` or the web equivalent). It already calls `resume_approval`.
5. Require the host probe in `scripts/engineering/m13_stage19_host_qualification.py` to exit 0 before treating a container result as qualification evidence.
6. Keep UNKNOWN when outcome persistence or the container result is uncertain. Do not reset the approval.

Tests that passed here used reference component authority and the label `TEST_ONLY`. They are not customer acceptance.

M13 remains open. M14 is not authorized.
