# Final test omission audit (v1.3.1 §21)

| Cat | Topic | Status | Notes |
|---:|---|---|---|
| A | In-place upgrade | **PARTIAL** | `test_historical_postgres_migrations.py` **8 passed** on isolated Postgres (0061 head, seeded org data); not full v1.3.0 binary upgrade. |
| B | Rollback safety | **PARTIAL** | Downgrade/re-upgrade covered in `test_historical_postgres_migrations` for supported revisions; full 0061→0060 product downgrade not promised — Alembic forward-only for production. |
| C | Backup and restore | **BLOCKED** | Isolated pg_dump/restore with populated enterprise fixture not automated in addendum harness; see `tests/test_historical_postgres_migrations.py` for data preservation proofs. |
| D | Long-run soak | **PARTIAL** | 120s health loop against `wp-hardening-smoke`; no server leak instrumentation. |
| E | Multi-worker distributed race | **PARTIAL** | Single-process pytest concurrency/race cases; not multi-uvicorn-worker live cluster. |
| F | Rolling restart | **BLOCKED** | No live multi-replica traffic + rolling restart harness on final SHA. |
| G | Paddle sandbox E2E | **BLOCKED** | No authorized sandbox credentials in environment for final SHA run. |
| H | MCP client interoperability | **PARTIAL** | In-process MCP dispatch tests only; Cursor Desktop / Streamable HTTP client E2E not run. |
| J | Legacy compatibility | **PARTIAL** | Canonical seams + web contract tests; rai:// aliases via static review in omission audit. |
| K | Authentication edge matrix | **PARTIAL** | Automated subset; WebAuthn/OAuth provider flows BLOCKED_EXTERNAL where noted in tests. |
| L | Email workflow | **BLOCKED** | No safe mail-capture provider configured in closure VM. |
| M | Limit / quota boundaries | **PARTIAL** | Billing/quota logic in unit tests; exact limit±1 concurrency not exhaustively proven live. |
| N | Hostile / large payloads | **PARTIAL** | MCP validation + SSRF tests; max body size soak not fully characterized. |
| O | HTTP / proxy boundary | **BLOCKED** | No local TLS reverse-proxy harness run on final SHA. |
| P | Container security scan | **BLOCKED** | Trivy on `responsibleai:95test` if image exists. |
| Q | Log/trace/metric secret review | **PARTIAL** | Transport boundary tests; no exhaustive log grep after synthetic secret injection. |
| R | Artifact consistency | **PASS** | Wheel build + version 1.3.1 in pyproject; container parity see compose artifact. |
| S | Multi-replica Kubernetes | **BLOCKED** | No kubectl/kind cluster (see Helm cluster acceptance). |
| T | Clock / expiry boundaries | **PARTIAL** | JWT/TOTP expiry covered in unit tests; fake-clock boundary sweep not run live. |
| U | Resource exhaustion / backpressure | **PARTIAL** | Trust outage → UNKNOWN fail-closed; full pool saturation not live-proven. |
| V | Partial side-effect / lost acknowledgement | **PARTIAL** | UNKNOWN disposition + restore reconcile tests; full external-success/lost-ACK live sim not run. |

## WHAT, IF ANYTHING, WAS NOT TESTED?

- **C. Backup and restore** — BLOCKED: Isolated pg_dump/restore with populated enterprise fixture not automated in addendum harness; see `tests/test_historical_postgres_migrations.py` for data preservation proofs.
- **F. Rolling restart** — BLOCKED: No live multi-replica traffic + rolling restart harness on final SHA.
- **G. Paddle sandbox E2E** — BLOCKED: No authorized sandbox credentials in environment for final SHA run.
- **L. Email workflow** — BLOCKED: No safe mail-capture provider configured in closure VM.
- **O. HTTP / proxy boundary** — BLOCKED: No local TLS reverse-proxy harness run on final SHA.
- **P. Container security scan** — BLOCKED: Trivy on `responsibleai:95test` if image exists.
- **S. Multi-replica Kubernetes** — BLOCKED: No kubectl/kind cluster (see Helm cluster acceptance).
- **A. In-place upgrade** — PARTIAL: PostgreSQL historical migration + seeded data preservation (not literal v1.3.0 semver binary).
- **B. Rollback safety** — PARTIAL: Downgrade/re-upgrade covered in `test_historical_postgres_migrations` for supported revisions; full 0061→0060 product downgrade not promised — Alembic forward-only for production.
- **E. Multi-worker distributed race** — PARTIAL: Single-process pytest concurrency/race cases; not multi-uvicorn-worker live cluster.
- **H. MCP client interoperability** — PARTIAL: In-process MCP dispatch tests only; Cursor Desktop / Streamable HTTP client E2E not run.
- **J. Legacy compatibility** — PARTIAL: Canonical seams + web contract tests; rai:// aliases via static review in omission audit.
- **K. Authentication edge matrix** — PARTIAL: Automated subset; WebAuthn/OAuth provider flows BLOCKED_EXTERNAL where noted in tests.
- **M. Limit / quota boundaries** — PARTIAL: Billing/quota logic in unit tests; exact limit±1 concurrency not exhaustively proven live.
- **N. Hostile / large payloads** — PARTIAL: MCP validation + SSRF tests; max body size soak not fully characterized.
- **Q. Log/trace/metric secret review** — PARTIAL: Transport boundary tests; no exhaustive log grep after synthetic secret injection.
- **T. Clock / expiry boundaries** — PARTIAL: JWT/TOTP expiry covered in unit tests; fake-clock boundary sweep not run live.
- **U. Resource exhaustion / backpressure** — PARTIAL: Trust outage → UNKNOWN fail-closed; full pool saturation not live-proven.
- **V. Partial side-effect / lost acknowledgement** — PARTIAL: UNKNOWN disposition + restore reconcile tests; full external-success/lost-ACK live sim not run.

## Soak artifact

See `WHITEPACT_V131_95_SOAK_REPORT.md`.

## OpenAPI artifact

See `WHITEPACT_V131_95_API_COMPATIBILITY_REPORT.md`.
