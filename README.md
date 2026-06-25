# ResponsibleAI

[![CI](https://github.com/Guruprasath-Annadurai/ResponsibleAi/actions/workflows/ci.yml/badge.svg)](https://github.com/Guruprasath-Annadurai/ResponsibleAi/actions)
[![PyPI version](https://img.shields.io/pypi/v/biasbuster)](https://pypi.org/project/biasbuster/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)](https://github.com/Guruprasath-Annadurai/ResponsibleAi)

**Enterprise AI Governance Platform — trust scoring, bias detection, guardrails, hallucination detection, compliance (NIST AI RMF / EU AI Act / ISO 42001), cost intelligence, and drift monitoring. Production-ready REST API included.**

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        ResponsibleAI  v0.6.0                                 │
│                                                                              │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Trust Score  │  │ Compliance  │  │  Guardrails  │  │  Hallucination   │  │
│  │ 6-dim A–F    │  │ NIST/EU/ISO │  │  PII + Tox   │  │  Self-consist.   │  │
│  └──────────────┘  └─────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Cost Intel   │  │   Red Team  │  │ Drift Monitor│  │   AI Passport    │  │
│  │ Route+Budget │  │ 10 attacks  │  │ Alerts+Trend │  │  SHA-256 cert    │  │
│  └──────────────┘  └─────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────────────────────────┐ │
│  │  BiasBuster  │  │ PrivacyLabel│  │         Governance Dashboard         │ │
│  │ 6 probes+CI  │  │  Federated  │  │  FastAPI · Auth · Rate limit · OTEL  │ │
│  └──────────────┘  └─────────────┘  └──────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## What this solves

Every team deploying AI in production faces the same gap: **no unified way to prove a model is safe, fair, and compliant.** Audits are manual, bias is discovered in production, compliance is a spreadsheet, and nobody knows what the LLM bill will be next month.

ResponsibleAI gives you one platform — a REST API, a Python SDK, and a live dashboard — that covers the full governance lifecycle:

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

---

## Install

```bash
# Governance platform + REST API
pip install "responsible-ai-platform[dashboard]"

# With PostgreSQL support
pip install "responsible-ai-platform[dashboard,postgres]"

# With Redis + OpenTelemetry
pip install "responsible-ai-platform[dashboard,redis,telemetry]"

# With LLM providers
pip install "responsible-ai-platform[dashboard,openai,anthropic]"

# Everything
pip install "responsible-ai-platform[all]"
```

---

## 30-second quickstart

```bash
# Start the governance dashboard
pip install "responsible-ai-platform[dashboard]"
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

Open `http://localhost:8765` for the live dashboard.

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

# Generate a verifiable AI Passport (SHA-256 signed certificate)
passport = PassportGenerator().generate(
    model_name="gpt-4o", provider="openai", trust_score=score,
    compliance_summary={"overall": 80.5},
)
print(passport.passport_id)      # rai-a3f7c2b1
print(passport.verification_hash[:16])  # 4d8e1f2a9c3b...
passport.export_html("passport.html")   # human-readable certificate
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
print(f"Consistency: {result.consistency_score:.2f}")
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
print(f"Violations: {len(report.violations)}")
for framework in report.frameworks:
    print(f"  {framework['name']}: {framework.get('status', 'evaluated')}")
```

### Red team simulation

```python
from responsibleai import RedTeamSimulator

simulator = RedTeamSimulator()
report = simulator.run_all()

print(f"Security score: {report.security_score:.1f}/100")
print(f"Vulnerabilities: {len(report.vulnerabilities)}")
print(f"Critical: {len(report.critical_vulnerabilities)}")
for v in report.critical_vulnerabilities:
    print(f"  [{v['cwe_id']}] {v['name']}: {v['description'][:60]}")
```

### Cost intelligence

```python
from responsibleai import CostTracker, ModelRouter, TokenUsage, BudgetPolicy

# Track real usage
tracker = CostTracker(db_path="~/.responsibleai/data.db",
                      policy=BudgetPolicy(monthly_limit_usd=500.0))
usage = TokenUsage.create(
    provider="openai", model="gpt-4o",
    input_tokens=2000, output_tokens=800, team="product",
)
record = tracker.record(usage)
print(f"This call: ${record.total_cost:.4f}")
print(f"Month to date: ${tracker.total_cost(30):.2f}")

budget = tracker.check_budget()
print(f"Budget: {budget.percentage_used:.1f}% used  Exceeded: {budget.is_exceeded}")

# Route tasks to the cheapest viable model
router = ModelRouter()
decision = router.route("Classify this email as spam or not spam", "balanced")
print(f"Complexity: {decision.complexity}")
print(f"Recommended: {decision.recommended_model}")
print(f"Estimated cost: ${decision.estimated_cost_per_1k:.4f}/1k tokens")
```

### Trust drift monitoring

```python
from responsibleai import TrustScoreEngine, TrustDriftMonitor

monitor = TrustDriftMonitor(db_path=":memory:", alert_threshold=5.0)
engine = TrustScoreEngine()

# Record scores over time — alert fires if score drops ≥ 5 points
for fairness in [0.90, 0.88, 0.85, 0.72]:   # gradual degradation
    score = engine.compute(fairness=fairness, privacy=0.85, security=0.80,
                           robustness=0.80, compliance=0.85, authenticity=0.85)
    alert = monitor.record("gpt-4o", "openai", score)
    if alert:
        print(f"Drift alert! {alert.severity}: {alert.delta:.1f} pt drop")

trend = monitor.trend("gpt-4o", "openai")
print(f"Direction: {trend['direction']}")   # degrading
print(f"7-day avg: {trend['7d_avg']}")
```

---

## Governance Dashboard

A production FastAPI application with a dark-mode SPA.

```bash
# Development
RAI_AUTH_ENABLED=false uvicorn responsibleai.dashboard.app:app --port 8765

# Production (with auth + persistent DB)
RAI_API_KEYS=your-key-here \
RAI_DB_PATH=/data/responsibleai.db \
uvicorn responsibleai.dashboard.app:app --host 0.0.0.0 --port 8765 --workers 4

# Docker
docker compose up -d
```

**Endpoints:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check with DB, auth, OTEL status |
| `GET` | `/api/metrics` | Uptime, request count, error rate, monthly spend |
| `POST` | `/api/evaluate` | Full model evaluation → trust score + compliance + passport |
| `GET` | `/api/trust-score/{model}/{provider}` | Score history + drift trend |
| `GET` | `/api/models` | All evaluated models |
| `POST` | `/api/scan` | Guardrails scan — PII detection + redaction |
| `POST` | `/api/hallucination` | Hallucination risk analysis |
| `POST` | `/api/cost/record` | Record token usage |
| `GET` | `/api/cost/summary` | Cost breakdown by model, team, day |
| `POST` | `/api/cost/analyze` | Prompt efficiency analysis — detect bloat |
| `POST` | `/api/cost/route` | Route a task to cheapest viable model |
| `GET` | `/api/cost/models` | Full model pricing catalogue |
| `GET` | `/api/drift/{model}/{provider}` | Drift trend + recent history |

Interactive API docs at `/api/docs`.

### Production features

| Feature | How |
|---|---|
| Authentication | Bearer token (`RAI_API_KEYS`) |
| Rate limiting | In-memory or Redis (`RAI_REDIS_URL`) |
| CORS | Configurable origins (`RAI_ALLOWED_ORIGINS`) |
| Security headers | CSP, X-Frame-Options, X-Content-Type-Options |
| Structured logging | JSON via structlog + request IDs |
| Database | SQLite (default) or PostgreSQL (`RAI_DATABASE_URL`) |
| Observability | OpenTelemetry traces + metrics (`RAI_OTEL_ENDPOINT`) |
| Exception handling | No raw stack traces ever reach clients |

---

## Docker

```bash
git clone https://github.com/Guruprasath-Annadurai/ResponsibleAi.git
cd ResponsibleAi

# Generate an API key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

cp .env.example .env
# Edit .env — set RAI_API_KEYS

docker compose up -d
# Dashboard at http://localhost:8765
# API docs at http://localhost:8765/api/docs
```

---

## PostgreSQL + Redis (horizontal scaling)

```bash
# .env
RAI_DATABASE_URL=postgresql://rai:secret@db-host:5432/responsibleai
RAI_REDIS_URL=redis://redis-host:6379/0
RAI_OTEL_ENDPOINT=http://otel-collector:4318

pip install "responsible-ai-platform[dashboard,postgres,redis,telemetry]"
```

The async database layer uses SQLAlchemy with connection pooling (`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`). Rate limiting switches automatically to Redis-backed storage when `RAI_REDIS_URL` is set.

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

**Scoring:** TF-IDF cosine divergence + length asymmetry + VADER sentiment divergence, with 95% bootstrap confidence intervals and intersectional co-failure amplification (×1.15).

---

## PrivacyLabel — on-device federated labeling

```python
from privacylabel import FederatedClient, FedAvgAggregator

client = FederatedClient(
    node_id="hospital-node-01",
    provider=MyProvider(),      # your local or API model
    epsilon_per_round=0.1,      # (ε, δ)-DP per round
    total_epsilon=1.0,          # 10 rounds before budget exhaustion
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
    pip install "responsible-ai-platform[openai]"
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
| `RAI_DB_PATH` | `~/.responsibleai/data.db` | SQLite path |
| `RAI_DATABASE_URL` | *(unset = SQLite)* | PostgreSQL URL for horizontal scaling |
| `RAI_API_KEYS` | *(empty = auth off)* | Comma-separated bearer tokens |
| `RAI_AUTH_ENABLED` | `true` | Toggle auth |
| `RAI_REDIS_URL` | *(unset = in-memory)* | Redis URL for distributed rate limiting |
| `RAI_RATE_LIMIT_DEFAULT` | `100/minute` | Global rate limit |
| `RAI_OTEL_ENDPOINT` | *(unset = disabled)* | OTLP HTTP endpoint |
| `RAI_OTEL_SERVICE_NAME` | `responsibleai` | Service name for traces |
| `RAI_ALERT_THRESHOLD` | `5.0` | Trust score drop that triggers drift alert |
| `RAI_MONTHLY_BUDGET_USD` | `10000.0` | Monthly AI spend limit |
| `RAI_LOG_LEVEL` | `INFO` | Log level |
| `RAI_LOG_JSON` | `true` | Structured JSON logs |
| `RAI_HOST` | `127.0.0.1` | Bind address |
| `RAI_PORT` | `8765` | Port |

Full reference in [.env.example](.env.example). Deployment guide in [DEPLOYMENT.md](DEPLOYMENT.md). SLA in [SLA.md](SLA.md).

---

## Development

```bash
git clone https://github.com/Guruprasath-Annadurai/ResponsibleAi.git
cd ResponsibleAi

python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Full test suite (637 tests, 90% coverage)
pytest

# Dashboard integration tests only
RAI_DB_PATH=:memory: RAI_AUTH_ENABLED=false pytest tests/test_dashboard_api.py

# Lint + type check
ruff check src/ tests/
mypy src/responsibleai src/biasbuster
```

637 tests, 90% line coverage across the trust engine, compliance framework, guardrails, hallucination detector, cost intelligence, drift monitor, async database layer, and governance API.

---

## Roadmap

- [x] v0.1 — BiasBuster: gender probe, 4 providers, CLI, CI integration
- [x] v0.2 — Racial / age / religious / occupational probes, HTML reporter, PrivacyLabel federated DP
- [x] v0.3 — Cultural bias, intersectional analysis, DeepfakeDetector ensemble
- [x] v0.4 — Cost Intelligence (CostTracker, ModelRouter, 16-model pricing), Trust Drift Monitor
- [x] v0.5 — Governance Dashboard (FastAPI), Trust Score, AI Passport, Guardrails, Hallucination, Compliance, Red Team, CI/CD, Docker, SLA
- [x] v0.6 — Async PostgreSQL (SQLAlchemy), Redis rate limiting, OpenTelemetry APM, LLM integration tests
- [ ] v0.7 — Real-time WebSocket drift alerts, Prometheus metrics endpoint, multi-tenant passport registry
- [ ] v1.0 — Managed cloud tier, SOC 2 audit trail, streaming aggregation server

---

## License

MIT — see [LICENSE](LICENSE).
