# WhitePact v1.3.1 — 9.5 engineering closure report

| Field | Value |
|-------|-------|
| Baseline SHA | `a471e497dba752812af7346efa341e5360ab5319` |
| Final SHA | `ac0ef1ef8093c516693f3b78426f7bd460f8590d` |
| Tree | `aacb6622feb865ebae42f8d32ef3a2814f4c4ab2` |
| Version | **1.3.1** (unchanged) |
| PR | **#114** (not merged) |

## Closure statement

**WHITEPACT 9.5 TECHNICAL CLOSURE CONDITIONAL — EVIDENCE GAPS REMAIN**

## CI / tests (pre-push on agent)

| Check | Status |
|-------|--------|
| Full CI on new HEAD | **PENDING** — must be green on final SHA after push |
| Security regression subset | **PASS** — 284 tests (`WHITEPACT_V131_95_SECURITY_REGRESSION.md`) |
| Prior RC CI (`a471e49`) | 16/16 green, 5002 passed (superseded once HEAD moves) |

## Area verdicts

| Area | Verdict | Notes |
|------|---------|-------|
| Python SDK live | **PASS** | Health + governed POST denial (legacy static key → 403 ANALYST) against Postgres-backed server |
| TypeScript SDK live | **PASS** | `npm install`, `tsc`, Node live health + connection refused |
| Go SDK live | **PASS** | `go test`, `go vet`, `cmd/livecheck` health |
| CLI matrix | **41/41 accounted** | Mix of REAL_ATTEMPT + HELP_ONLY; not all verbs exercised from installed wheel venv |
| Wheel install | **PASS** | `python -m build` wheel, fresh venv, `whitepact` console script, `alembic.ini` in site-packages |
| Browser matrix | **PASS** (shallow) | Chromium/Firefox/WebKit × desktop/tablet/mobile; route load only — **not** full login/approval journey |
| Docker Compose | **PARTIAL** | Build PASS; runtime DB TCP blocked VM-side (`WHITEPACT_V131_95_COMPOSE_ACCEPTANCE.md`) |
| Helm cluster | **BLOCKED** | No kubectl/kind/minikube; `helm lint` + `helm template` run |
| Performance | **LOCAL-CONTAINER** | Concurrency sweep 1–100 documented; not production-scale |
| MCP benchmark | **AUTHORITATIVE SCRIPT** | `PRODUCTION_TOOL_DEFS` via `run_v131_production_tool_benchmarks.py` |
| Security | **PASS** (subset) | No regression in curated list; full suite awaits CI |
| Billing | **PASS** (subset) | `test_paddle_billing_service.py` in regression set |
| Tenant isolation | **PASS** (subset) | `test_tenant_isolation.py` |
| Evidence / replay | **NOT RE-RUN LIVE** | Covered by pytest subset only in this campaign |
| Observability drill | **PARTIAL** | Bad API key + health paths only |
| Stranger test | **PARTIAL** | Documentation path; wheel migrate path improved |
| Helm icon P3 | **OPEN** | No stable public logo URL added to `Chart.yaml` |

## Remaining gaps (honest)

| Priority | Count | Items |
|----------|------:|-------|
| P0 | 0 | — |
| P1 | 1 | Full CI green on **new** final SHA |
| P2 | 4 | Compose runtime proof on operator host; Helm live cluster; CLI from wheel-only venv; deep browser auth journeys |
| P3 | 1 | Helm chart icon |

## Code / packaging changes (this campaign)

- `pyproject.toml` — ship `alembic.ini` + `migrations/` in wheel (`force-include`).
- `Dockerfile` — copy migration assets into builder stage (fixes image wheel build).
- `sdk/typescript/src/client.ts` — TypeScript 5 `URLSearchParams` tuple typing (build unblock).
- `scripts/run_v131_95_quality_closure.py` — live evidence orchestrator.
- `scripts/v131_95_browser_matrix.mjs` — Playwright matrix.
- `sdk/go/cmd/livecheck/` — Go live health probe.

**Semantic version:** Still **1.3.1** — packaging and closure harness only; no Gate B / Phase7A / MCP tool count changes.

## External customer validation

**NOT YET AVAILABLE — REQUIRES REAL PILOTS** (not a software defect)

## Artifacts

`WHITEPACT_V131_95_*.md` at repo root; copies under `release-evidence/v131_95/` and `/opt/cursor/artifacts/v131_95/`.
