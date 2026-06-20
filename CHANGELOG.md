# Changelog

All notable changes to this project are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
