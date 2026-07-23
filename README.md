<p align="center">
  <a href="https://github.com/Guruprasath-Annadurai/ResponsibleAi/actions"><img src="https://github.com/Guruprasath-Annadurai/ResponsibleAi/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  <a href="https://pypi.org/project/biasbuster/"><img src="https://img.shields.io/pypi/v/biasbuster" alt="PyPI version"/></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"/></a>
  <a href="https://github.com/Guruprasath-Annadurai/ResponsibleAi"><img src="https://img.shields.io/badge/tests-942_passing-brightgreen.svg" alt="942 tests passing"/></a>
</p>

<p align="center"><strong>Enterprise AI Governance Platform — trust scoring, bias detection, guardrails, hallucination detection, compliance (NIST AI RMF / EU AI Act / ISO 42001), cost intelligence, drift monitoring, and MCP server for Claude Code integration.</strong></p>

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        ResponsibleAI  v1.1.0                                 │
│                                                                              │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Trust Score  │  │ Compliance  │  │  Guardrails  │  │  Hallucination   │  │
│  │ 6-dim A–F    │  │ NIST/EU/ISO │  │  PII + Tox   │  │  Self-consist.   │  │
│  └──────────────┘  └─────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Cost Intel   │  │   Red Team  │  │ Drift Monitor│  │   AI Passport    │  │
│  │ Route+Budget │  │ 10 attacks  │  │ Alerts+Trend │  │  SHA-256 cert    │  │
│  └──────────────┘  └─────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  BiasBuster  │  │ PrivacyLabel│  │  MCP Server  │  │  Audit Log API   │  │
│  │ 6 probes+CI  │  │  Federated  │  │  26 tools    │  │  Export+Summary  │  │
│  └──────────────┘  └─────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │   Governance Dashboard — FastAPI · Per-org rate limit · Alembic · OTEL  │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## What this solves

Every team deploying AI in production faces the same gap: **no unified way to prove a model is safe, fair, and compliant.** Audits are manual, bias is discovered in production, compliance is a spreadsheet, and nobody knows what the LLM bill will be next month.

ResponsibleAI gives you one platform — a REST API, a Python SDK, an MCP server, and a live dashboard — that covers the full governance lifecycle:

| Problem | Module | Output |
|---|---|---|
| Is this model trustworthy? | `TrustScoreEngine` | 0–100 score, A–F grade, risk level |
| Does it comply with regulations? | `ComplianceEngine` | NIST AI RMF, EU AI Act tier, ISO 42001 |
| Is it exposing PII? | `GuardrailsEngine` | Block / redact with audit log |
| Is it hallucinating? | `HallucinationDetector` | Risk score, unsupported claims |
| Can it be attacked? | `RedTeamSimulator` | 10 vectors, CVE IDs, safe-refusal rate |
| How much is it costing? | `CostTracker` + `ModelRouter` | Per-model USD, routing to cheapest viable model |
| Is it getting worse over time? | `TrustDriftMonitor` | 7/30-day trend, severity alerts |
| Is it biased? | `BiasBuster` | 6 demographic probes, CI gate |
| Is this data labeled privately? | `PrivacyLabel` | Federated DP labels, never leaves device |
| Is this media real? | `DeepfakeDetector` | Ensemble confidence, method detected |
| Can any MCP client govern every AI call? | `MCP Server` | 26 governance tools over stdio or HTTP+SSE |

---

## Install

```bash
# Governance platform + REST API
pip install "rai-governance-platform[dashboard]"

# With PostgreSQL support
pip install "rai-governance-platform[dashboard,postgres]"

# With Redis + OpenTelemetry
pip install "rai-governance-platform[dashboard,redis,telemetry]"

# With LLM providers
pip install "rai-governance-platform[dashboard,openai,anthropic]"

# Everything
pip install "rai-governance-platform[all]"
```

---

## 30-second quickstart

```bash
# Start the governance dashboard
pip install "rai-governance-platform[dashboard]"
uvicorn responsibleai.dashboard.app:app --port 8765

# Evaluate a model (no LLM key needed — supply your own scores)
curl -X POST http://localhost:8765/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "gpt-4o",
    "provider": "openai",
    "fairness": 0.80,
    "privacy": 0.85,
    "security": 0.82,
    "robustness": 0.78,
    "compliance": 0.90,
    "authenticity": 0.88
  }'
```

```json
{
  "trust_score": { "trust_score": 83.65, "grade": "B", "risk": "LOW" },
  "compliance": { "overall_score": 80.5, "eu_ai_act_tier": "limited_risk", "violations": 0 },
  "passport_id": "rai-a3f7c2b1",
  "passport_hash": "4d8e1f2a9c3b7e6d...",
  "drift_alert": null
}
```

Open `http://localhost:8765` for the live dashboard and `http://localhost:8765/api/docs` for interactive API docs.

---

## MCP Server — govern every AI call from Claude Code, Claude Desktop, or any MCP client

The MCP (Model Context Protocol) server exposes ResponsibleAI as **26 tools and
10 resources** to any MCP-compatible client — Claude Code, Claude Desktop,
Cursor, Windsurf, or your own agent runtime. When a team's client points at
this server, every AI interaction is automatically governed — trust scoring,
guardrails, compliance checks (NIST AI RMF / EU AI Act / ISO 42001), bias
evaluation, drift detection, cost tracking, and audit logging run on any call
without code changes.

### Setup

```bash
# Install
pip install "rai-governance-platform[dashboard,mcp]"

# Start the REST API (MCP tools call it internally)
RAI_DB_PATH=/var/lib/rai/governance.db \
RAI_API_KEYS=your-key-here \
uvicorn responsibleai.dashboard.app:app --host 127.0.0.1 --port 8765 &

# Add to Claude Code (~/.claude/claude_desktop_config.json or via /mcp)
```

```json
{
  "mcpServers": {
    "responsibleai": {
      "command": "responsibleai-mcp",
      "env": {
        "RAI_API_URL": "http://localhost:8765",
        "RAI_API_KEY": "your-key-here"
      }
    }
  }
}
```

### Available tools (26)

| Tool | What it does |
|---|---|
| `rai_scan` | Detect and redact PII + harmful content before it reaches a log |
| `rai_trust_score` | Composite AI Trust Score (0-100) across 6 governance dimensions |
| `rai_compliance` | NIST AI RMF / EU AI Act / ISO 42001 compliance evaluation |
| `rai_hallucination` | Hallucination risk from hedging, consistency, unsupported claims |
| `rai_cost_estimate` | USD cost of a model API call from token counts |
| `rai_redteam_payloads` | Adversarial attack payloads (prompt injection, jailbreak, etc.) |
| `rai_redteam_analyze` | Security report from model responses to red team payloads |
| `rai_compare_models` | Compare two models across all 6 trust dimensions |
| `rai_audit_summary` | Governance capability summary (tools, frameworks, attack vectors) |
| `rai_health` | Status and module availability of the governance engine |
| `rai_bias_evaluate` | Demographic bias across 6 probe dimensions with confidence intervals |
| `rai_drift_check` | Trust score drift between a baseline and current evaluation |
| `rai_passport_generate` | Verifiable, tamper-evident AI Passport for vendor risk assessment |
| `rai_budget_check` | Spend vs. budget, per-team/model breakdown, month-end projection |
| `rai_policy_check` | Text/response against a governance policy (blocklists, disclaimers) |
| `rai_stream_scan` | PII/harm scan across streaming LLM output chunks |
| `rai_benchmark` | Score responses against truthfulqa / bbq / hellaswag suites |
| `rai_benchmark_prompts` | Question set for a benchmark suite |
| `rai_model_route` | Cheapest model that can handle a task, with cost/quality tradeoff |
| `rai_pii_report` | PII audit report by category with GDPR/CCPA remediation guidance |
| `rai_incident_log` | Structured governance incident record for audit/SIEM |
| `rai_eu_ai_act_classify` | EU AI Act risk tier classification with compliance roadmap |
| `rai_iso42001_gap` | ISO/IEC 42001:2023 AI Management System gap analysis |
| `rai_executive_summary` | Board-ready governance summary with RAG status indicators |
| `rai_org_status` | Governance status snapshot: models, grades, compliance, risk |
| `rai_webhook_status` | Webhook delivery health, failure analysis, remediation actions |

### Available resources (10)

| Resource | URI | Contents |
|---|---|---|
| Health | `rai://health` | Current health status of the governance service |
| Model pricing catalog | `rai://models/catalog` | Supported models with per-token pricing |
| Compliance frameworks | `rai://compliance/frameworks` | NIST AI RMF, EU AI Act, ISO 42001 |
| Red team categories | `rai://redteam/categories` | Adversarial attack categories |
| Trust dimensions | `rai://trust/dimensions` | The 6 dimensions behind the Trust Score |
| Bias probe catalog | `rai://bias/probes` | Available bias probes and scoring interpretation |
| Governance policy template | `rai://governance/policy` | Default policy template for `rai_policy_check` |
| Trust grade reference | `rai://trust/grades` | Grade thresholds, risk tiers, deployment guidance |
| NIST AI RMF checklist | `rai://compliance/checklist/nist` | Actionable NIST implementation checklist |
| EU AI Act checklist | `rai://compliance/checklist/eu-ai-act` | Compliance checklist for high-risk operators |

---

## Python SDK

### Trust scoring

```python
from responsibleai import TrustScoreEngine, PassportGenerator

engine = TrustScoreEngine()
score = engine.compute(
    fairness=0.80, privacy=0.85, security=0.82,
    robustness=0.78, compliance=0.90, authenticity=0.88,
)
print(f"{score.overall:.1f} / 100  Grade: {score.grade}  Risk: {score.risk_level}")
# → 83.7 / 100  Grade: B  Risk: LOW

passport = PassportGenerator().generate(
    model_name="gpt-4o", provider="openai", trust_score=score,
    compliance_summary={"overall": 80.5},
)
print(passport.passport_id)
passport.export_html("passport.html")
```

### Guardrails — block PII before it reaches a log

```python
from responsibleai import GuardrailsEngine

guardrails = GuardrailsEngine()
result = guardrails.scan("Customer SSN is 123-45-6789, email: alice@company.com")

print(result.is_blocked)      # True
print(result.pii_count)       # 2
print(result.redacted_text)   # "Customer SSN is [SSN], email: [EMAIL]"
```

### Hallucination detection

```python
from responsibleai import HallucinationDetector

detector = HallucinationDetector()
result = detector.analyze(
    "AI will replace all human jobs by 2025.",
    candidates=[
        "AI will automate some repetitive tasks.",
        "AI creates new job categories alongside displacing others.",
    ],
)
print(f"Risk: {result.hallucination_risk:.2f}  Level: {result.risk_level}")
```

### Compliance — NIST AI RMF, EU AI Act, ISO 42001

```python
from responsibleai import ComplianceEngine

engine = ComplianceEngine()
report = engine.evaluate(
    fairness_score=0.80, privacy_score=0.85,
    security_score=0.82, robustness_score=0.78,
    compliance_maturity=0.90, use_case="credit_scoring",
)
print(f"Score: {report.compliance_score * 100:.1f}%")
print(f"EU AI Act tier: {report.eu_ai_act_tier.value}")  # high_risk
```

### Red team simulation

```python
from responsibleai import RedTeamSimulator

simulator = RedTeamSimulator()
report = simulator.run_all()

print(f"Security score: {report.security_score:.1f}/100")
print(f"Vulnerabilities: {len(report.vulnerabilities)}")
for v in report.critical_vulnerabilities:
    print(f"  [{v['cwe_id']}] {v['name']}")
```

### Cost intelligence

```python
from responsibleai import CostTracker, ModelRouter, TokenUsage, BudgetPolicy

tracker = CostTracker(db_path="~/.responsibleai/data.db",
                      policy=BudgetPolicy(monthly_limit_usd=500.0))
usage = TokenUsage.create(
    provider="openai", model="gpt-4o",
    input_tokens=2000, output_tokens=800, team="product",
)
record = tracker.record(usage)
print(f"This call: ${record.total_cost:.4f}")
print(f"Month to date: ${tracker.total_cost(30):.2f}")

router = ModelRouter()
decision = router.route("Classify this email as spam or not spam", "balanced")
print(f"Recommended: {decision.recommended_model}  ${decision.estimated_cost_per_1k:.4f}/1k tokens")
```

### Trust drift monitoring

```python
from responsibleai import TrustScoreEngine, TrustDriftMonitor

monitor = TrustDriftMonitor(db_path=":memory:", alert_threshold=5.0)
engine = TrustScoreEngine()

for fairness in [0.90, 0.88, 0.85, 0.72]:
    score = engine.compute(fairness=fairness, privacy=0.85, security=0.80,
                           robustness=0.80, compliance=0.85, authenticity=0.85)
    alert = monitor.record("gpt-4o", "openai", score)
    if alert:
        print(f"Drift alert! {alert.severity}: {alert.delta:.1f} pt drop")
```

---

## Governance Dashboard

A production FastAPI application with a dark-mode SPA.

```bash
# Development (auth off, SQLite in-memory)
RAI_AUTH_ENABLED=false uvicorn responsibleai.dashboard.app:app --port 8765

# Production (auth + persistent DB)
RAI_API_KEYS=your-key-here \
RAI_DB_PATH=/data/responsibleai.db \
uvicorn responsibleai.dashboard.app:app --host 0.0.0.0 --port 8765 --workers 4

# Docker
docker compose up -d
```

### REST API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health — DB, auth, OTEL, version |
| `GET` | `/api/metrics` | Uptime, request count, error rate, monthly spend |
| `POST` | `/api/evaluate` | Full evaluation → trust + compliance + passport |
| `GET` | `/api/trust-score/{model}/{provider}` | Score history + drift trend |
| `GET` | `/api/models` | All evaluated models |
| `POST` | `/api/scan` | Guardrails — PII detection + redaction |
| `POST` | `/api/hallucination` | Hallucination risk analysis |
| `POST` | `/api/cost/record` | Record token usage |
| `GET` | `/api/cost/summary` | Cost breakdown by model / team / day |
| `POST` | `/api/cost/analyze` | Prompt efficiency — detect bloat |
| `POST` | `/api/cost/route` | Route task to cheapest viable model |
| `GET` | `/api/cost/models` | Full model pricing catalogue |
| `GET` | `/api/drift/{model}/{provider}` | Drift trend + history |
| `GET` | `/api/audit` | Paginated audit log (org-scoped) |
| `GET` | `/api/audit/export` | Export audit log as JSONL or CSV |
| `GET` | `/api/audit/summary` | Audit counts grouped by endpoint |
| `GET` | `/api/redteam/payloads` | Red team payload library (10 vectors) |
| `POST` | `/api/redteam/analyze` | Analyze model responses for vulnerabilities |
| `GET` | `/api/billing/usage` | Token spend and budget status |
| `GET` | `/api/leaderboard` | Public cross-model trust leaderboard (no auth) |
| `GET` | `/api/leaderboard/{model}/{provider}/history` | Trend over time for one model (no auth) |
| `GET` | `/api/leaderboard/{model}/{provider}/diagnostic` | Per-prompt findings — PRO plan required |
| `POST` | `/api/trust-index/assess` | Free, public self-assessment against the open Trust Index standard |
| `GET` | `/api/trust-index/verify/{passport_id}` | Verify a cited Trust Index score (no auth) |
| `GET` | `/api/trust-index/certified` | Directory of certified passports (no auth) |
| `POST` | `/api/trust-index/certify/{passport_id}` | Certify a passport — super-admin only |

Interactive docs at `/api/docs`. Public leaderboard page at `/leaderboard` —
see `compliance/LEADERBOARD_METHODOLOGY.md` for the published scoring
methodology and `scripts/run_leaderboard_eval.py` to run evaluations. Open
Trust Index standard and passport verification at `/verify/{id}` — see
`compliance/TRUST_INDEX_SPEC.md`.

### Production features

| Feature | Detail |
|---|---|
| Authentication | Bearer token (`RAI_API_KEYS`) with RBAC (OWNER / ADMIN / ANALYST / VIEWER) |
| Per-org rate limiting | Each Bearer token gets its own rate limit bucket (SHA-256 keyed) — no shared global pool |
| CORS | Configurable origins (`RAI_ALLOWED_ORIGINS`) |
| Security headers | CSP, X-Frame-Options, X-Content-Type-Options |
| Structured logging | JSON via structlog + request IDs |
| Database | SQLite (default) or PostgreSQL (`RAI_DATABASE_URL`) with Alembic migrations |
| Observability | OpenTelemetry traces + metrics (`RAI_OTEL_ENDPOINT`) |
| Webhooks | HMAC-signed delivery with DB-persisted retry queue (survives restarts) |
| Exception handling | No raw stack traces reach clients |

---

## Database migrations (Alembic)

Schema changes are managed with Alembic. The initial migration creates all 8 tables.

```bash
# Upgrade to latest schema
RAI_DB_PATH=/var/lib/rai/governance.db alembic upgrade head

# PostgreSQL
RAI_DB_URL=postgresql://user:pass@host:5432/responsibleai alembic upgrade head

# Show migration history
alembic history

# Generate a new migration after changing engine.py
alembic revision --autogenerate -m "add_new_column"
```

All migrations use `render_as_batch=True` so they run on both SQLite and PostgreSQL without changes.

---

## Webhook notifications

Register an endpoint and receive signed events when governance thresholds fire.

```bash
# Register a Slack webhook
curl -X POST http://localhost:8765/api/webhooks \
  -H "Authorization: Bearer your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ops-slack",
    "url": "https://hooks.slack.com/services/...",
    "events": ["drift_alert", "budget_exceeded", "guardrail_triggered"],
    "provider": "slack",
    "secret": "hmac-secret-for-signature-verification",
    "max_retries": 5
  }'
```

Deliveries are persisted to the database. If the server restarts during a retry cycle, the background worker picks up where it left off on next boot. Retry schedule: 1 s → 5 s → 30 s → 2 min → 10 min.

Verify payloads with the `X-RAI-Signature-256: sha256=<hex>` header.

---

## Docker

```bash
git clone https://github.com/Guruprasath-Annadurai/ResponsibleAi.git
cd ResponsibleAi

python3 -c "import secrets; print(secrets.token_urlsafe(32))"

cp .env.example .env
# Edit .env — set RAI_API_KEYS

docker compose up -d
# Dashboard: http://localhost:8765
# API docs:  http://localhost:8765/api/docs
```

---

## PostgreSQL + Redis (horizontal scaling)

```bash
# .env
RAI_DATABASE_URL=postgresql://rai:secret@db-host:5432/responsibleai
RAI_REDIS_URL=redis://redis-host:6379/0
RAI_OTEL_ENDPOINT=http://otel-collector:4318

pip install "rai-governance-platform[dashboard,postgres,redis,telemetry]"

# Run migrations before first start
RAI_DB_URL=postgresql://rai:secret@db-host:5432/responsibleai alembic upgrade head
```

The async database layer uses SQLAlchemy with connection pooling (`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`). Rate limiting switches to Redis-backed storage when `RAI_REDIS_URL` is set.

---

## BiasBuster — bias evaluation in CI

```bash
# Fail CI when demographic bias exceeds threshold
biasbuster run \
  --provider openai --model gpt-4o \
  --probes gender-bias,racial-bias,cultural-bias \
  --threshold 0.20 \
  --output report --format html
```

```python
from biasbuster import BiasBusterRunner, GenderBiasProbe, RacialBiasProbe
from biasbuster.providers import OpenAIProvider
import asyncio

async def main():
    provider = OpenAIProvider(api_key="sk-...", model="gpt-4o")
    runner = BiasBusterRunner(provider=provider)
    suite = await runner.run([
        GenderBiasProbe(threshold=0.20),
        RacialBiasProbe(threshold=0.20),
    ])
    print(f"Score: {suite.overall_score:.4f}  {'PASSED' if suite.passed else 'FAILED'}")

asyncio.run(main())
```

**Available probes:** `gender-bias`, `racial-bias`, `age-bias`, `religious-bias`, `occupational-stereotype`, `cultural-bias`

**Scoring:** TF-IDF cosine divergence + length asymmetry + VADER sentiment divergence, 95% bootstrap confidence intervals, intersectional co-failure amplification (×1.15).

---

## PrivacyLabel — on-device federated labeling

```python
from privacylabel import FederatedClient, FedAvgAggregator

client = FederatedClient(
    node_id="hospital-node-01",
    provider=MyProvider(),
    epsilon_per_round=0.1,
    total_epsilon=1.0,
    delta=1e-6,
    gradient_clip=1.0,
)
# Raw data stays on disk — only privatised gradients leave the device
summary = await client.train_round("data/local_records.jsonl")
print(f"Privacy budget used: ε={summary.privacy_spent['spent_epsilon']:.3f}")
```

Implements Laplace, Gaussian, Exponential, and DP-SGD mechanisms. Byzantine-robust aggregation via Weiszfeld geometric median.

---

## GitHub Actions — bias gate in CI

```yaml
- name: Bias evaluation
  run: |
    pip install "rai-governance-platform[openai]"
    biasbuster run \
      --provider openai --model gpt-4o-mini \
      --probes gender-bias,racial-bias,cultural-bias \
      --threshold 0.20
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `RAI_DB_PATH` | `governance.db` | SQLite path |
| `RAI_DB_URL` | *(unset = SQLite)* | Full SQLAlchemy URL — takes priority over `RAI_DB_PATH` |
| `RAI_DATABASE_URL` | *(unset)* | Alias for `RAI_DB_URL` |
| `RAI_API_KEYS` | *(empty = auth off)* | Comma-separated bearer tokens |
| `RAI_AUTH_ENABLED` | `true` | Toggle auth enforcement |
| `RAI_REDIS_URL` | *(unset = in-memory)* | Redis URL for distributed rate limiting |
| `RAI_RATE_LIMIT_DEFAULT` | `100/minute` | Per-org rate limit (keyed by Bearer token) |
| `RAI_OTEL_ENDPOINT` | *(unset = disabled)* | OTLP HTTP endpoint |
| `RAI_OTEL_SERVICE_NAME` | `responsibleai` | Service name for traces |
| `RAI_ALERT_THRESHOLD` | `5.0` | Trust score drop that triggers drift alert |
| `RAI_MONTHLY_BUDGET_USD` | `10000.0` | Monthly AI spend limit |
| `RAI_LOG_LEVEL` | `INFO` | Log level |
| `RAI_LOG_JSON` | `true` | Structured JSON logs |
| `RAI_HOST` | `127.0.0.1` | Bind address |
| `RAI_PORT` | `8765` | Port |

---

## Development

```bash
git clone https://github.com/Guruprasath-Annadurai/ResponsibleAi.git
cd ResponsibleAi

python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Full test suite (942 tests, 86% coverage)
pytest

# Dashboard tests only
RAI_DB_PATH=:memory: RAI_AUTH_ENABLED=false pytest tests/test_dashboard_api.py

# Webhook persistence tests
pytest tests/test_webhook_persistence.py

# MCP server tests
pytest tests/test_mcp_server.py

# Lint + type check
ruff check src/ tests/
mypy src/responsibleai src/biasbuster
```

---

## Roadmap

- [x] v0.1 — BiasBuster: gender probe, 4 providers, CLI, CI integration
- [x] v0.2 — Racial / age / religious / occupational probes, HTML reporter, PrivacyLabel federated DP
- [x] v0.3 — Cultural bias, intersectional analysis, DeepfakeDetector ensemble
- [x] v0.4 — Cost Intelligence (CostTracker, ModelRouter, 16-model pricing), Trust Drift Monitor
- [x] v0.5 — Governance Dashboard (FastAPI), Trust Score, AI Passport, Guardrails, Hallucination, Compliance, Red Team, CI/CD, Docker, SLA
- [x] v0.6 — Async PostgreSQL (SQLAlchemy), Redis rate limiting, OpenTelemetry APM, LLM integration tests
- [x] v1.0 — WebSocket drift alerts, Prometheus endpoint, multi-tenant RBAC, org management API
- [x] v1.1 — MCP server (10 tools, 5 resources), audit log API, red team API, billing API, Alembic migrations, per-org rate limiting, DB-persisted webhook retry queue
- [ ] v1.2 — Streaming response scanner, multi-region DB replication, SOC 2 audit export
- [ ] v2.0 — Managed cloud tier, real-time aggregation server, ML-based drift prediction

---

## License

MIT — see [LICENSE](LICENSE).
