# Changelog

All notable changes to this project are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
