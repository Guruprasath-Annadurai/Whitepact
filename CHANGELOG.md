# Changelog

All notable changes to this project are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-06-26

### Added
- **Stable versioned API** — all breaking changes frozen after this release
  - `GET /api/version` — returns version, stability metadata, and changelog URL
  - `/api/v1/*` URL prefix supported via transparent rewrite middleware (no redirect overhead)
  - `X-API-Version: 1.0.0` and `X-API-Min-Version: 1.0.0` response headers on every call
  - Health endpoint reports `api_versions`, `stable_since` fields
- **Single Sign-On — OAuth2 / OIDC** (`responsibleai.auth`)
  - `OIDCProvider` — async JWKS caching, JWT validation (RS256/RS384/RS512/ES256/ES384/ES512)
  - `AsyncJWKSClient` — fetches and caches JSON Web Key Sets with 1-hour TTL
  - `JWTClaims` — frozen dataclass: `sub`, `email`, `name`, `roles`, `org_id`
  - Discovery document auto-fetch from `{issuer}/.well-known/openid-configuration`
  - New config fields: `oidc_issuer`, `oidc_client_id`, `oidc_client_secret`, `oidc_redirect_uri`, `oidc_scopes`, `oidc_jwks_uri`, `oidc_skip_verification`
  - `GET /api/auth/providers` — list configured auth providers
  - `GET /api/auth/login/{provider_id}` — initiate OAuth2 authorization code flow
  - `GET /api/auth/callback` — exchange code, validate token, return claims
  - `POST /api/auth/logout` — invalidate session
- **SLA-backed support tier**
  - `GET /api/support` — three-tier support table (Standard / Professional / Enterprise) with uptime SLAs and response times
  - `GET /api/support/status` — public platform status page (no auth required)
  - SLA.md updated with full support tier breakdown and direct contact info
- **Kubernetes Helm chart** (`helm/rai-governance/`)
  - `Deployment` with pod anti-affinity, non-root security context, read-only root filesystem
  - `HorizontalPodAutoscaler` — CPU + memory targets, 2–10 replicas
  - `PodDisruptionBudget` — minimum 1 available during rolling updates
  - `Ingress` with TLS and nginx annotations
  - `PersistentVolumeClaim` for SQLite data persistence
  - `ConfigMap` + `Secret` for all `RAI_*` env vars and OIDC secrets
  - `ServiceAccount` with `automountServiceAccountToken: false`
- **Multi-language SDKs**
  - **Python SDK** (`sdk/python/rai_client/`) — async `RAIClient` using `httpx`, full type hints, frozen response dataclasses for `TrustScore`, `GuardrailScan`, `HallucinationAnalysis`, `ComplianceReport`, `CostRecord`, `EvalCompareResult`
  - **TypeScript SDK** (`sdk/typescript/`) — `RAIClient` using Fetch API (Node 18+ / browser), full TypeScript types, zero runtime dependencies
  - **Go SDK** (`sdk/go/raiclient/`) — `Client` using `net/http`, context-aware, zero external dependencies
- New optional dependency group: `sso` (`PyJWT[crypto]>=2.8.0`)

### Changed
- Version bumped `0.9.0 → 1.0.0`
- `Development Status :: 4 - Beta` → `5 - Production/Stable` in PyPI classifiers
- App description updated to mention SSO, versioned stable API
- `modules` list in health endpoint updated with `sso_oidc`, `api_versioning`, `support`

**802 tests passing · 87% coverage**

---

## [0.9.0] — 2026-06-26

### Added
- **Model Evaluation Framework** (`responsibleai.eval`)
  - **`ModelComparator`** — side-by-side A/B comparison of two models on identical prompts
    - Per-prompt trust scoring via TrustScoreEngine; PII and hallucination penalties applied
    - `ComparisonResult` with per-prompt breakdown, aggregate winner, win/tie counts
    - `POST /api/eval/compare` — accepts prompt set + two response sets, persists result
  - **`BenchmarkRunner`** — runs three built-in benchmark suites against pre-collected responses
    - **TruthfulQA** (15 samples) — factual accuracy via keyword matching
    - **BBQ** (15 samples) — social bias detection across gender, race, age, religion, disability
    - **HellaSwag** (15 samples) — commonsense reasoning / sentence completion
    - `BenchmarkResult` with accuracy, bias_rate, overall_score, per-category breakdown
    - `POST /api/eval/benchmark` — runs suite, optionally sets result as baseline, checks regressions
    - `GET /api/eval/benchmark/prompts/{suite}` — returns prompt list for feeding to any model
  - **`RegressionDetector`** — tracks per-model baselines and flags score drops between runs
    - Three severity levels: `MINOR` (≥1%), `MODERATE` (≥5%), `SEVERE` (≥15%)
    - Monitors accuracy drop, bias_rate rise, and overall_score drop independently
    - `GET /api/eval/regression/{model}` — returns in-memory and DB-persisted baselines
  - **`DatasetBiasScanner`** — scans CSV/JSONL/text datasets for bias markers and PII
    - Six bias categories: gender, racial, age, religious, occupational, socioeconomic
    - PII detection via GuardrailsEngine; toxicity flagging included
    - `scan_csv()`, `scan_jsonl()`, `scan_texts()` interfaces
    - `DatasetScanResult` with flag_rate, per-category counts, flagged sample preview
    - `POST /api/eval/dataset-scan` — accepts text list, returns full scan summary
- **`EvalRepository`** (`responsibleai.db.EvalRepository`)
  - Persists comparison runs, benchmark runs, and dataset scans to `eval_runs` table
  - Persists model baselines to `eval_baselines` table with upsert semantics
  - `GET /api/eval/results` — list stored runs, filterable by type/model/org
- **Two new DB tables**: `eval_runs`, `eval_baselines`
- **50 new tests**: `tests/test_eval.py`

### Changed
- Version bumped `0.8.0 → 0.9.0`
- Dashboard description updated; `eval_compare`, `eval_benchmarks`, `eval_regression`, `dataset_scan` added to modules list

**802 tests passing · 87% coverage**

---

## [0.8.0] — 2026-06-25

### Added
- **Multi-tenant org management** (`responsibleai.rbac`, `responsibleai.db.OrgRepository`)
  - `Organization` model — id, name, slug, per-org monthly budget cap
  - `POST /api/orgs` (OWNER only), `GET /api/orgs`, `GET /api/orgs/{id}`, `DELETE /api/orgs/{id}`
  - DB table: `organizations`
- **DB-backed API keys with RBAC** (`responsibleai.db.OrgRepository`)
  - Keys stored as SHA-256 hashes — raw key shown once on creation, never stored
  - `POST /api/orgs/{id}/keys`, `GET /api/orgs/{id}/keys`, `DELETE /api/orgs/{id}/keys/{key_id}`
  - Revoked keys retained in DB for audit trail
  - `last_used_at` updated on every authenticated request
  - DB table: `org_api_keys`
- **Role-Based Access Control** (`responsibleai.rbac`)
  - Four roles: `OWNER > ADMIN > ANALYST > VIEWER`
  - `require_role(Role.X)` FastAPI dependency factory enforces minimum role on every endpoint
  - `has_permission()` hierarchical comparison helper
  - Backward compatible — flat `RAI_API_KEYS` entries treated as OWNER
- **`OrgContext`** — injected into every authenticated request via `Depends(get_org_context)`; carries `org_id`, `role`, `key_id`, `is_legacy`
- **Governance audit log** (`responsibleai.db.AuditRepository`)
  - Every API request recorded: endpoint, method, status, duration, IP, request_id, org_id, key_id
  - `GET /api/audit-log` (ADMIN+) — filterable by org, endpoint, date range; paginated
  - `endpoint_summary()` — top-N endpoints by request count with avg latency
  - `cleanup(retention_days)` — delete entries older than N days
  - DB table: `audit_log`
- **`AuditLogMiddleware`** — non-blocking async write via `asyncio.ensure_future`; skips `/static` and `/metrics`
- **ContextVar** (`_audit_ctx`) — passes org/key context from auth dependency to audit middleware without coupling
- **`/api/metrics`** now reports `audit_entries_30d`
- **`/api/health`** now reports `orgs` count
- **69 new tests**: `tests/test_rbac.py` (30) + `tests/test_org_api.py` (20) + `tests/test_audit_log.py` (19)

### Changed
- Version bumped `0.7.0 → 0.8.0`
- All endpoints use `require_role(Role.X)` instead of legacy `_require_auth`; backward-compatible
- CORS allows `PUT` and `DELETE` methods

**752 tests passing · 88% coverage**

---

## [0.7.0] — 2026-06-25

### Added
- **WebSocket live dashboard** (`/ws/dashboard`)
  - Real-time push of trust score updates, drift alerts, cost events, and guardrail blocks
  - Auth via `?token=<api-key>` query param; unauthenticated connections rejected with code 4001
  - Per-API-key tenant isolation — each client only receives its own events
  - Background heartbeat ping every 30 s with live connection count
  - Initial state snapshot sent on connect (monthly spend, registered models)
- **Streaming LLM scanner** (`responsibleai.streaming`)
  - `StreamingScanner` wraps any `AsyncIterator[str]` (OpenAI / Anthropic stream or custom generator)
  - Scans every N tokens (configurable `scan_window`, default 50) and on sentence boundaries
  - Hard-stop mode — terminates the stream immediately on PII detection
  - `StreamScanSummary` with token count, scan count, PII detections, elapsed ms
  - Async context-manager and plain async-generator interfaces
- **Enterprise webhook system** (`responsibleai.webhooks`)
  - `WebhookManager` — register, remove, list, test endpoints
  - Event types: `drift_alert`, `budget_exceeded`, `guardrail_triggered`, `trust_score_changed`
  - HMAC-SHA256 payload signing (`X-RAI-Signature-256` header)
  - Exponential backoff retry: 1 s / 5 s / 30 s (configurable `max_retries`)
  - Concurrent fan-out via `asyncio.gather`
  - Provider-specific payload formatters: Slack Block Kit, Teams Adaptive Card, PagerDuty Events API v2, generic JSON
  - In-memory delivery log (last 1 000 entries) with success/failure counters
- **Prometheus `/metrics` endpoint**
  - Metrics: `rai_trust_score`, `rai_requests_total`, `rai_cost_usd_total`, `rai_tokens_total`, `rai_guardrail_scans_total`, `rai_drift_alerts_total`, `rai_active_ws_connections`, `rai_webhook_deliveries_total`
  - Labeled by `model`, `provider`, `severity`, `result`, etc.
  - Compatible with Prometheus, Grafana, Datadog agent, VictoriaMetrics
- **Webhook CRUD API** — `POST/GET/DELETE /api/webhooks`, `GET /api/webhooks/deliveries`, `POST /api/webhooks/test/{id}`
- **`/api/health`** now reports `websocket_connections` and `webhooks_registered`
- **`/api/metrics`** now reports `websocket_connections`, `webhooks_registered`, `webhook_deliveries`, `webhook_failures`
- **46 new tests**: `tests/test_streaming.py` (17) + `tests/test_webhooks.py` (29)
- New optional deps: `websockets>=12.0`, `prometheus-client>=0.20.0`

### Changed
- Version bumped `0.6.0 → 0.7.0`
- `dashboard` dep group includes `websockets` and `prometheus-client`
- CORS allows `PUT` and `DELETE` methods (webhook management)

**683 tests passing · 88% coverage**

---

## [0.6.0] — 2026-06-20

### Added
- **Async database layer** (`responsibleai.db`)
  - `DatabaseEngine` — SQLAlchemy async engine factory; auto-selects `sqlite+aiosqlite` (default)
    or `postgresql+asyncpg` when `RAI_DATABASE_URL` is set
  - `CostRepository` — async replacement for CostTracker's DB operations; identical surface area,
    fully awaitable, connection-pooled (`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`)
  - `TrustRepository` — async replacement for TrustDriftMonitor's DB operations; drift detection,
    trend analysis, model listing
  - WAL mode + `synchronous=NORMAL` applied automatically for SQLite
- **Redis distributed rate limiting** — set `RAI_REDIS_URL=redis://host:6379/0` to switch slowapi
  from in-memory to Redis storage; falls back to in-memory when unset
- **OpenTelemetry APM** (`responsibleai.dashboard.telemetry`)
  - Traces and metrics exported via OTLP HTTP (`RAI_OTEL_ENDPOINT`)
  - FastAPI and HTTPX auto-instrumented via `opentelemetry-instrumentation-*`
  - Custom spans/metrics: `evaluate_model`, `ai.trust_score` histogram, `ai.guardrail.scans`
    counter, `ai.cost.usd` and `ai.tokens.total` counters
  - Compatible with Datadog, Grafana Tempo, Jaeger, and any OTLP collector
  - No-op fallback when `RAI_OTEL_ENDPOINT` is not set (zero overhead)
- **Dashboard upgraded to v0.6.0**
  - `/api/health` now reports `db_backend`, `rate_limit_backend`, `otel` status
  - `/api/metrics` now includes `monthly_spend_usd`, `db_backend`, `otel_enabled`
  - All DB operations in endpoints are now fully async
- **New environment variables**: `RAI_DATABASE_URL`, `RAI_REDIS_URL`, `RAI_OTEL_ENDPOINT`,
  `RAI_OTEL_SERVICE_NAME`, `RAI_OTEL_HEADERS`
- **New optional dep groups**: `postgres` (`asyncpg`), `redis` (`limits[redis]`),
  `telemetry` (full OTEL stack)
- **LLM integration tests** (`tests/test_llm_integration.py`) — 17 tests covering the full
  governance pipeline with mocked OpenAI and Anthropic API calls; no real keys required
- **Async DB tests** (`tests/test_async_db.py`) — 29 tests for `CostRepository` and
  `TrustRepository` using SQLite+aiosqlite; PostgreSQL path skipped when asyncpg absent

### Changed
- Version bumped `0.5.0 → 0.6.0`
- Dashboard endpoints fully migrated from sync CostTracker/TrustDriftMonitor to async repositories
- `pyproject.toml`: new optional groups, `all` updated to include `postgres`, `redis`, `telemetry`

### Fixed
- `app.py`: replaced deprecated `@app.on_event` with modern `asynccontextmanager` lifespan pattern

---

## [0.5.0] — 2025-06-20

### Added
- **Production-grade Governance Dashboard** (`responsibleai.dashboard`)
  - API key authentication (Bearer token, configurable via `RAI_API_KEYS`)
  - Per-endpoint rate limiting via `slowapi` (configurable per env var)
  - Structured JSON request logging with `structlog` and request IDs
  - Security response headers (`X-Content-Type-Options`, `X-Frame-Options`, etc.)
  - Global exception handlers — no raw stack traces leaked to clients
  - Pydantic-Settings config (`RAI_*` env vars, `.env` file support)
  - `/api/metrics` endpoint — uptime, request count, error rate, config status
  - Improved `/api/health` with database connectivity check
  - Input validation with strict size caps on all request fields
  - Graceful startup/shutdown lifecycle (closes SQLite connections cleanly)
- **Persistent storage by default** — DB path `~/.responsibleai/data.db`; `:memory:` for tests
- **CI/CD pipeline** (`.github/workflows/`)
  - `ci.yml` — lint (ruff), type-check (mypy), pytest with 80% coverage gate, build check
  - `publish.yml` — PyPI trusted publisher, triggers on `git tag v*`
- **Docker** — multi-stage `Dockerfile`, `docker-compose.yml` with persistent volume
- **`.env.example`** — full environment variable reference
- **`DEPLOYMENT.md`** — Docker, bare-metal, nginx reverse proxy, auth, backup instructions
- **`SLA.md`** — uptime tiers, response time targets, incident classification, data retention
- **`CHANGELOG.md`** — this file

### Changed
- Version bumped `0.4.0 → 0.5.0`
- `pyproject.toml`: added `dashboard` optional dep group, updated classifiers, added Changelog URL
- CI workflow updated to cover `src/responsibleai` with 80% minimum coverage gate
- Dashboard `app.py` fully rewritten with auth, middleware, rate limiting, validation, lifecycle hooks

### Fixed
- `drift/monitor.py`: removed stray `@dataclass_like = None` syntax error

---

## [0.4.0] — 2025-06-19

### Added
- **Cost Intelligence module** (`responsibleai.cost`)
  - `CostTracker` — SQLite-backed token usage, budget enforcement, team/model breakdown
  - `CostAnalyzer` — prompt bloat detection, model overkill detection, verbose response detection
  - `ModelRouter` — routes tasks to cheapest acceptable model by complexity tier
  - `MODEL_CATALOG` — 16 models with real 2025 pricing (OpenAI, Anthropic, Google, Mistral, Cohere, Ollama)
- **Trust Drift Monitor** (`responsibleai.drift`)
  - `TrustDriftMonitor` — SQLite-backed trust score history, drift alerts with severity levels
  - `trend()` — 7-day and 30-day moving averages, direction detection
- **Governance Dashboard** — FastAPI backend + dark-mode SPA (Chart.js + Tailwind)
- **Examples** — 7 self-contained scripts covering all platform modules, no API keys required
- 74 new tests; full suite 559 passing at 85% coverage

---

## [0.3.0] — 2025-06-18 (pre-open-source)

### Added
- **TrustScoreEngine** — 6-dimension composite score (0–100, A–F grade, risk level)
- **AIPassport** — SHA-256 verifiable trust certificate, JSON + HTML export
- **GuardrailsEngine** — PII detection (6 types), toxicity filtering, in-place redaction
- **HallucinationDetector** — TF-IDF self-consistency + hedging density
- **ComplianceEngine** — NIST AI RMF (14 controls), ISO 42001 (8 controls), EU AI Act tier classification
- **RedTeamSimulator** — 10 adversarial attack vectors, CWE IDs, safe-refusal detection
- 485 tests, 88% coverage on `responsibleai` package

---

## [0.2.0] — 2025-06-15 (pre-open-source)

### Added
- `PrivacyLabel` — federated data labeling with differential privacy
  - `FederatedClient` with `epsilon_per_round` / `total_epsilon` budget tracking
  - 4 DP mechanisms: Laplace, Gaussian, Exponential, DP-SGD
  - `FedAvgAggregator` with Weiszfeld geometric median
- `DeepfakeDetector` — MEAN/MAX/WEIGHTED/MAJORITY ensemble voting
- Cultural bias probe and intersectional co-failure analysis

---

## [0.1.0] — 2025-06-10 (pre-open-source)

### Added
- `BiasBuster` — 6 demographic bias probes (gender, racial, age, religious, occupational, cultural)
- TF-IDF cosine divergence + VADER sentiment scoring
- Bootstrap confidence intervals for divergence estimates
