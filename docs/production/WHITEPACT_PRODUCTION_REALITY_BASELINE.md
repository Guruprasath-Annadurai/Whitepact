# WhitePact Production Reality Baseline (Launch Cell B)

**Program:** Launch Cell B — corporate production infrastructure & operations  
**Branch:** `feature/whitepact-production-platform-observability`  
**Audited baseline:** `origin/main` @ `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` (Gate 3 frozen)  
**Product version (pyproject):** `1.3.1`  
**Alembic migration head (filename):** `0061_sovereign_shadow_observations.py`  
**Audit method:** code + existing CI tests (not live production deployment)

## Executive summary

WhitePact has **substantial production-oriented code** (Postgres compose, Helm, production `Settings` fail-closed validators, restore admission gate, OTEL hooks, backup scripts). **Corporate launch qualification is not complete**: full Postgres backup/restore rehearsal, load/soak evidence, and production DR proof remain **NOT_TESTED** in this program's first milestone.

## Subsystem classification

| Subsystem | Classification | Evidence |
|-----------|----------------|----------|
| `Dockerfile` (multi-stage, non-root, HEALTHCHECK) | REAL_BUT_PARTIAL | Built in CI reproducible-build job; not full container scan evidence in this doc |
| `docker-compose.prod.yml` | REAL_BUT_PARTIAL | Postgres+Redis+dashboard; requires `.env.prod`; not auto-proven restore |
| `helm/rai-governance/` | REAL_BUT_PARTIAL | Probes, securityContext, HPA, migration job templates; `helm lint` in CI |
| `Settings` / env contract (`dashboard/config.py`) | REAL_AND_TESTED | `tests/test_config.py`, enterprise preflight tests |
| Alembic migrations | REAL_AND_TESTED | CI + extensive DB tests |
| Dashboard `/api/health`, `/readyz`, `/livez` | REAL_AND_TESTED | `tests/test_v1_api.py`, restore admission tests |
| MCP HTTP `/health` | REAL_BUT_PARTIAL | `mcp/server.py`; hosted production preflight |
| Restore admission / reconciliation | REAL_AND_TESTED | `backup_defense.py`, `tests/test_restore_*` |
| `scripts/backup-postgres.sh` / `restore-postgres.sh` | REAL_BUT_PARTIAL | Scripts exist; **restore not rehearsed** in CI |
| Structured logging (structlog / JSON) | REAL_BUT_PARTIAL | Config flag `WHITEPACT_LOG_JSON`; privacy sweep tests |
| OpenTelemetry | REAL_BUT_PARTIAL | `tests/test_telemetry.py`; optional endpoint |
| Prometheus metrics | REAL_BUT_PARTIAL | Health mentions module; not full SLO stack |
| Rate limiting (Redis vs memory) | REAL_AND_TESTED | `multi_replica_problems()` + tests |
| Governance execution / nonce / revocation | REAL_AND_TESTED | Hosted path DB repos; concurrency tests |
| Formula Ω∞ enforcement infra flag | MISSING | Gate 8+; no `FORMULA_ENFORCEMENT` env on main |
| IOT / Device Bridge | MISSING | Out of scope on main |
| Corporate on-call paging integration | MISSING | Runbooks only (this program) |
| Paid observability vendor | NOT_APPLICABLE | Vendor-neutral interfaces |

## How production is intended to run

See `WHITEPACT_PRODUCTION_ARCHITECTURE.md`. Canonical path: **TLS edge → dashboard (8765) + MCP (8766) → Postgres + Redis → governance runtime**.

## P0 / P1 (launch blockers from audit)

**P0 (unchanged until independent review):**

- No claim of production deployment performed.
- Cross-tenant isolation must remain proven on each release (existing test suites; not re-run as full pen-test).

**P1:**

- Postgres **restore rehearsal** not recorded as PASS.
- **Load/soak** evidence not produced in Cell B milestone 1.
- **Formula rollout** control plane env not wired (expected until Gate 8).

## Next milestones

Phases B1–B12 per master directive; this commit delivers **B0 audit + B1 partial (contract module + docs skeleton)**.
