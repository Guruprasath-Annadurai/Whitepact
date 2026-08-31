<!-- mcp-name: io.github.Guruprasath-Annadurai/whitepact -->
<p align="center">
  <a href="https://github.com/Guruprasath-Annadurai/Whitepact/actions"><img src="https://github.com/Guruprasath-Annadurai/Whitepact/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  <a href="https://pypi.org/project/rai-governance-platform/"><img src="https://img.shields.io/pypi/v/rai-governance-platform" alt="PyPI version"/></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"/></a>
  <a href="https://registry.modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP_Registry-listed-blue.svg" alt="Listed on the official MCP Registry"/></a>
  <a href="https://smithery.ai/server/guruprasathannadurai-official/whitepact"><img src="https://img.shields.io/badge/Smithery-listed-blue.svg" alt="Listed on Smithery"/></a>
  <a href="https://scorecard.dev/viewer/?uri=github.com/Guruprasath-Annadurai/Whitepact"><img src="https://api.scorecard.dev/projects/github.com/Guruprasath-Annadurai/Whitepact/badge" alt="OpenSSF Scorecard"/></a>
  <a href="https://www.bestpractices.dev/projects/14112"><img src="https://www.bestpractices.dev/projects/14112/badge" alt="OpenSSF Best Practices"/></a>
  <a href="https://www.bestpractices.dev/projects/14112"><img src="https://www.bestpractices.dev/projects/14112/baseline" alt="OpenSSF Baseline"/></a>
</p>

<p align="center"><strong>WhitePact — an independent runtime authority, governance, and assurance layer for autonomous systems: a five-way governance decision engine (ALLOW / ALLOW_WITH_REDACTION / REQUIRE_APPROVAL / DENY / QUARANTINE), trust scoring, bias detection, guardrails, hallucination detection, compliance mapping (NIST AI RMF / EU AI Act / ISO 42001), cost intelligence, drift monitoring, a public Trust Index / leaderboard / AI Incident Database, and an MCP server (30 tools, 20 resources) with LangChain, LangGraph, and Google ADK trust-gate integrations.</strong></p>

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        WhitePact  v1.2.6                                     │
│                                                                              │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Governance   │  │ Trust Score │  │  Compliance  │  │  Guardrails      │  │
│  │ 5-way decide │  │ 6-dim A–F   │  │ NIST/EU/ISO  │  │  PII + Tox       │  │
│  └──────────────┘  └─────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Hallucination│  │ Cost Intel  │  │   Red Team   │  │  Drift Monitor   │  │
│  │ Self-consist.│  │ Route+Budget│  │ 10 attacks   │  │  Alerts+Trend    │  │
│  └──────────────┘  └─────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ AI Passport  │  │  BiasBuster │  │ PrivacyLabel │  │  MCP Server      │  │
│  │ SHA-256 cert │  │ 6 probes+CI │  │  Federated   │  │  30 tools/HTTP   │  │
│  └──────────────┘  └─────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │   Governance Dashboard — FastAPI · Per-org rate limit · Alembic · OTEL  │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## What this solves

Every team deploying AI in production faces the same gap: **no unified way to
prove a model — or an autonomous agent's actions — is safe, fair, compliant,
and accountable.** Audits are manual, bias is discovered in production,
compliance is a spreadsheet, an agent's tool calls go ungoverned, and nobody
knows what the LLM bill will be next month.

WhitePact gives you one platform — a REST API, a Python SDK, an MCP server,
and a live dashboard — that covers the full governance lifecycle:

| Problem | Module | Output |
|---|---|---|
| Should this agent action be allowed, redacted, held for approval, denied, or quarantined? | `WhitePactRuntimeGateway` (governance core) | A five-way `GovernanceDecision`, deterministic, no LLM call in the decision path |
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
| Can I trust a third-party MCP server before connecting to it? | `SupplyChainScanner` | VERIFIED_FACT / INFERRED_SIGNAL / UNKNOWN verdicts — typosquat, description-content, known-incident checks |
| Is there a tamper-evident record of every governance decision? | `EvidenceRepository` | Hash-chained `EvidenceRecord`, per-org, `verify_chain()` |
| Does a risky action get a human in the loop? | `ApprovalRepository` | Race-safe `PENDING → APPROVED/DENIED` workflow |
| How does this model rank against others, independently? | `Public Leaderboard` | Cross-model trust ranking from actually calling each model's API, not self-reported |
| Can I cite and verify a trust score anywhere? | `Trust Index` | Free self-assessed or human-reviewed certified passport, verifiable at `/verify/{id}`, embeddable badge |
| Has this AI system failed publicly before? | `AI Incident Database` | Crowd-reported, moderator-reviewed, hash-chained public registry |
| Should my agent trust this third-party tool before calling it? | `rai_check_trust` + LangChain/LangGraph/ADK integrations | Free lookup, plus a real block/pause gate in-agent |
| Can any MCP client govern every AI call? | `MCP Server` | 27 governance tools over stdio, Streamable HTTP, or legacy HTTP+SSE |

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

The published PyPI package name (`rai-governance-platform`) and the import
name (`responsibleai`) predate the WhitePact rename and are kept as-is —
see `MIGRATION_WHITEPACT_V2.md` Section 3 for why an alias package
(`whitepact`) was added instead of renaming the published package outright.

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

Open `http://localhost:8765` for the live dashboard and
`http://localhost:8765/api/docs` for interactive API docs.

---

## Governance core — five-way decisions, not a binary block/allow

`src/responsibleai/governance/` (see `SPEC.md` Sections 4-8 for the full
architecture contract) is a deterministic runtime authority sitting in front
of agent tool calls:

```python
from responsibleai.governance import WhitePactRuntimeGateway, ActionRequest, AuthorityContext

gateway = WhitePactRuntimeGateway()
result = gateway.evaluate(
    action=ActionRequest(tool_name="rai_scan", arguments={"text": "..."}),
    authority=AuthorityContext(org_id="acme", agent_id="agent-1"),
)
print(result.decision)  # GovernanceDecision.ALLOW | ALLOW_WITH_REDACTION | REQUIRE_APPROVAL | DENY | QUARANTINE
```

- **Risk tiering** (`governance/risk.py`) — every MCP tool is classified
  against a hardcoded, drift-tested table, not inferred at call time.
- **Policy engine** (`governance/policy.py`) — first-match-wins rules with
  `ALLOW` / `DENY` / `REQUIRE_APPROVAL` effects.
- **Evidence** (`governance/evidence.py`) — every decision is written to a
  per-org, hash-chained `EvidenceRecord`; `verify_chain()` detects tampering.
  Raw argument values are never stored, only field-name keys.
- **Approval workflow** (`governance/approval.py`) — `REQUIRE_APPROVAL`
  decisions queue a real, race-safe `ApprovalRequest` with a resolution API,
  not just a log line.
- **Supply-chain scanner** (`src/responsibleai/supplychain/`) — before an
  agent trusts a third-party MCP server or tool, `SupplyChainScanner` returns
  one of three explicit verdicts (`VERIFIED_FACT` / `INFERRED_SIGNAL` /
  `UNKNOWN`) — never a single opaque trust score — from typosquat detection,
  tool-description scanning, and known-incident cross-reference.
- **Identity Bridge** (`integrations/identity_bridge.py`) — maps Entra ID,
  Google Workspace, Okta, and AWS (Cognito / IAM Identity Center) ID token
  claims into `IdentityContext`, plus `map_groups_to_authority()` to turn
  IdP group membership into a granted-action-types `AuthorityContext`. See
  `MACHINE_AUTHORITY_V1.md`'s Identity Bridge section for exactly what's
  verified (claim-shape correctness against each provider's public docs)
  versus not (live-tenant testing, Graph/Admin-SDK group-name resolution,
  AWS's non-JWT SigV4 path).

No governance decision is LLM-based; see
`DETERMINISTIC_VS_PROBABILISTIC.md` for why.

**See it end-to-end**: `examples/08_whitepact_enterprise_scenario.py` runs a
full scenario (an org onboarding an autonomous finance agent) through all
eight machine-authority invariants — ceiling, delegation, attenuation,
approval quorum, workflow composition, autonomy budget, memory firewall,
evidence bundle — against real code, no API keys required:

```bash
python examples/08_whitepact_enterprise_scenario.py
```

---

## MCP Server — govern every AI call from Claude Code, Claude Desktop, or any MCP client

The MCP (Model Context Protocol) server exposes WhitePact as **30 tools and
20 resources** (10 canonical resource URIs, dual-advertised under both
`whitepact://` and `rai://` schemes — see `MIGRATION_WHITEPACT_V2.md`) to any
MCP-compatible client — Claude Code, Claude Desktop, Cursor, Windsurf, or your
own agent runtime. Three transports are supported: stdio, Streamable HTTP
(`/mcp`, current MCP spec), and legacy HTTP+SSE (`/sse` + `/messages/`, kept
for older clients). When a team's client points at this server, every AI
interaction is automatically governed — five-way governance decisions, trust
scoring, guardrails, compliance checks (NIST AI RMF / EU AI Act / ISO 42001),
bias evaluation, drift detection, cost tracking, and hash-chained audit
evidence run on any call without code changes.

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
    "whitepact": {
      "command": "whitepact-mcp",
      "env": {
        "RAI_API_URL": "http://localhost:8765",
        "RAI_API_KEY": "your-key-here"
      }
    }
  }
}
```

`whitepact-mcp` and `responsibleai-mcp` are the same entry point — see
`pyproject.toml`'s `[project.scripts]`; both will keep working, use whichever
name you prefer.

### Available tools (27)

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
| `rai_check_trust` | Free public Trust Index lookup for a **third-party** model/tool, before an agent invokes it — unlike every other tool above, which evaluates output the caller itself produced |

### Agent-framework integrations — LangChain, LangGraph, Google ADK

`src/responsibleai/integrations/` wires `rai_check_trust` directly into three
agent frameworks so an agent can be gated on a tool's public trust score
before invoking it, not just log the call after the fact:

- **LangChain** (`langchain_middleware.py`) — `TrustGateMiddleware`, a
  `wrap_tool_call` middleware that blocks a call outright when its score is
  below threshold. Requires `pip install "rai-governance-platform[langchain]"`.
- **LangGraph** (`langgraph_gate.py`) — `make_trust_gate_node()`, a node that
  pauses the graph with `interrupt()` for a human approve/reject decision on
  a below-threshold call, instead of a hard block. Requires
  `pip install "rai-governance-platform[langgraph]"`.
- **Google ADK** (`adk_toolset.py`) — `build_stdio_toolset()` /
  `build_http_toolset()`, thin factories over ADK's `McpToolset`, which
  auto-discovers this project's MCP server's tools with no custom glue code.
  Requires `pip install "rai-governance-platform[adk]"`.

All three, or any subset, install via `pip install "rai-governance-platform[agent-frameworks]"`.
See `GAME_CHANGER_BUILD_PLAN.md` Phase B for the reasoning behind each.

### Available resources (20)

10 canonical resources, each advertised under both the `whitepact://` and
`rai://` URI schemes (dual scheme is additive — see
`MIGRATION_WHITEPACT_V2.md`; the table below shows the canonical URI):

| Resource | URI | Contents |
|---|---|---|
| Health | `whitepact://health` | Current health status of the governance service |
| Model pricing catalog | `whitepact://models/catalog` | Supported models with per-token pricing |
| Compliance frameworks | `whitepact://compliance/frameworks` | NIST AI RMF, EU AI Act, ISO 42001 |
| Red team categories | `whitepact://redteam/categories` | Adversarial attack categories |
| Trust dimensions | `whitepact://trust/dimensions` | The 6 dimensions behind the Trust Score |
| Bias probe catalog | `whitepact://bias/probes` | Available bias probes and scoring interpretation |
| Governance policy template | `whitepact://governance/policy` | Default policy template for `rai_policy_check` |
| Trust grade reference | `whitepact://trust/grades` | Grade thresholds, risk tiers, deployment guidance |
| NIST AI RMF checklist | `whitepact://compliance/checklist/nist` | Actionable NIST implementation checklist |
| EU AI Act checklist | `whitepact://compliance/checklist/eu-ai-act` | Compliance checklist for high-risk operators |

### MCP directory listings

WhitePact is listed and queryable today on real MCP directories — not
aspirational, all verified live:

- **Official MCP Registry** — `server.json` at the repository root
  (schema `2025-12-11`, listing version `1.2.3`) is published as
  `io.github.Guruprasath-Annadurai/whitepact`, confirmed queryable at
  [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io).
  Advertises both the PyPI/stdio package (`whitepact-mcp`, self-hosted,
  free, unrestricted) and a `remotes` entry pointing at the hosted
  Streamable HTTP and SSE transports (`whitepact-mcp-http.onrender.com`)
  — a one-click remote connector, not just an installable package.
- **Antigravity CLI plugin** — `plugins/whitepact/` at the repository
  root follows the [official Antigravity plugin manifest
  format](https://antigravity.google/docs/plugins), connecting to the
  same hosted Streamable HTTP transport via `serverUrl`. No official
  Antigravity plugin directory exists yet, so this is distributed
  directly from the repo — see `plugins/whitepact/README.md`.
- **Smithery** — listed as
  [`guruprasathannadurai-official/whitepact`](https://smithery.ai/server/guruprasathannadurai-official/whitepact),
  30 tools and 20 resources discovered against the hosted Streamable
  HTTP transport (`whitepact-mcp-http.onrender.com/mcp`, a separate
  Render service from the main dashboard). This deployment has no
  OAuth authorization server configured — only static Bearer API
  keys — so a public, unauthenticated
  `/.well-known/mcp/server-card.json` serves the same live
  `TOOL_DEFS`/`RESOURCE_DEFS` the server itself advertises, for
  directories whose scanners can't complete a live authenticated
  crawl.

See `compliance/MCP_DISTRIBUTION_GUIDE.md` for the full distribution
plan, including directories not yet submitted to.

### Platform integrations

WhitePact connects to the major AI platforms as one MCP server through
standards-compliant clients — no per-platform forks, no per-platform
governance logic. See [`docs/integrations/`](docs/integrations/) for the
canonical compatibility matrix (`PLATFORM_COMPATIBILITY.md`), per-platform
setup docs (GitHub Copilot, Microsoft Copilot, Claude, Grok, Gemini,
Amazon Q, AWS Bedrock AgentCore, Mistral Le Chat, Cursor), and
`FOUNDER_ACTIONS.md` for what still needs a human. Run
`python scripts/integration_smoke.py` for a live protocol-level preflight
against the hosted endpoint.

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

A production FastAPI application with a dark-mode SPA. A live instance is
hosted at **[whitepact.com](https://whitepact.com)**.

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
| `GET` | `/api/trust-index/check` | Free, public — trust score + incident count for a named model/tool, by exact name (no auth); what `rai_check_trust` and the LangChain/LangGraph/ADK integrations call |
| `GET` | `/api/trust-index/registry` | Every assessed model/tool, certified and self-reported, newest first (no auth) — data source for the public `/registry` page |
| `GET` | `/api/trust-index/certified` | Directory of certified passports (no auth) |
| `POST` | `/api/trust-index/certify/{passport_id}` | Certify a passport — super-admin only |
| `GET` | `/api/trust-index/badge/{passport_id}.svg` | Embeddable trust badge (Self-Assessed / Certified), no auth |
| `POST` | `/api/incident-db/report` | Report a publicly observed AI incident (no auth, rate-limited) |
| `GET` | `/api/incident-db` | Browse published incidents — filter by model, provider, severity, type (no auth) |
| `GET` | `/api/incident-db/check` | Pre-deployment exact-match incident check for a model/provider — PRO/ENTERPRISE |
| `GET` | `/api/incident-db/verify` | Recompute the hash chain over every published entry (no auth) |
| `POST` | `/api/orgs/{org_id}/keys/{key_id}/mfa/enroll` | Enroll an API key in TOTP MFA |
| `POST` | `/api/orgs/{org_id}/keys/{key_id}/mfa/verify` | Verify a TOTP code / backup code |
| `GET`/`POST` | `/api/governance/evidence` | Read/write hash-chained governance evidence records |
| `GET`/`POST` | `/api/governance/approvals` | Queue and resolve `REQUIRE_APPROVAL` decisions |

Interactive docs at `/api/docs`. Public leaderboard page at `/leaderboard` —
see `compliance/LEADERBOARD_METHODOLOGY.md` for the published scoring
methodology and `scripts/run_leaderboard_eval.py` to run evaluations. Open
Trust Index standard and passport verification at `/verify/{id}` — see
`compliance/TRUST_INDEX_SPEC.md`. Free, zero-signup self-assessment at
`/assess`; browse every assessed model/tool at `/registry`. `/llms.txt`
points AI crawlers/answer engines at these as canonical sources — see
`GAME_CHANGER_STRATEGY.md` for why.

### Production features

| Feature | Detail |
|---|---|
| Authentication | Bearer token (`RAI_API_KEYS`) with RBAC (OWNER / ADMIN / ANALYST / VIEWER) |
| MFA | TOTP (RFC 6238) on the interactive login step, org-enforceable, single-use backup codes |
| Field-level encryption | Opt-in (`RAI_FIELD_ENCRYPTION_KEY`) on `audit_log.ip_address`, incident reporter contact info, webhook secrets, MFA secrets — with key-rotation support (`MultiFernet`) |
| Per-org rate limiting | Each Bearer token gets its own rate limit bucket (SHA-256 keyed) — no shared global pool |
| CORS | Configurable origins (`RAI_ALLOWED_ORIGINS`) |
| Security headers | CSP, X-Frame-Options, X-Content-Type-Options |
| Structured logging | JSON via structlog + request IDs |
| Database | SQLite (default) or PostgreSQL (`RAI_DATABASE_URL`) with Alembic migrations |
| Observability | OpenTelemetry traces + metrics (`RAI_OTEL_ENDPOINT`) |
| Webhooks | HMAC-signed delivery with DB-persisted retry queue (survives restarts) |
| Exception handling | No raw stack traces reach clients |
| Governance evidence | Hash-chained, per-org, tamper-evident (`GET /api/governance/evidence`) |

---

## Database migrations (Alembic)

Schema changes are managed with Alembic. Run `alembic history` for the
current, authoritative migration count and table list — this number changes
frequently enough that a hardcoded count here goes stale fast; the command
itself is the source of truth.

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

All migrations use `render_as_batch=True` so they run on both SQLite and
PostgreSQL without changes.

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

Deliveries are persisted to the database. If the server restarts during a
retry cycle, the background worker picks up where it left off on next boot.
Retry schedule: 1 s → 5 s → 30 s → 2 min → 10 min.

Verify payloads with the `X-RAI-Signature-256: sha256=<hex>` header.

---

## Docker

```bash
git clone https://github.com/Guruprasath-Annadurai/Whitepact.git
cd Whitepact

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

The async database layer uses SQLAlchemy with connection pooling
(`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`). Rate limiting
switches to Redis-backed storage when `RAI_REDIS_URL` is set.

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

Dual-prefixed `WHITEPACT_*` equivalents for these are also read where
`MIGRATION_WHITEPACT_V2.md` documents them — the `RAI_*` names remain the
primary, always-supported form.

---

## Development

```bash
git clone https://github.com/Guruprasath-Annadurai/Whitepact.git
cd Whitepact

python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Full test suite (run it to see the current test count and coverage —
# see CONTRIBUTING.md's Running Tests section for why no number is
# hardcoded here)
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

See [`ROADMAP.md`](ROADMAP.md) for the canonical NOW/NEXT/LATER plan. The list below is a historical, version-by-version changelog summary kept for reference.

- [x] v0.1 — BiasBuster: gender probe, 4 providers, CLI, CI integration
- [x] v0.2 — Racial / age / religious / occupational probes, HTML reporter, PrivacyLabel federated DP
- [x] v0.3 — Cultural bias, intersectional analysis, DeepfakeDetector ensemble
- [x] v0.4 — Cost Intelligence (CostTracker, ModelRouter, 16-model pricing), Trust Drift Monitor
- [x] v0.5 — Governance Dashboard (FastAPI), Trust Score, AI Passport, Guardrails, Hallucination, Compliance, Red Team, CI/CD, Docker, SLA
- [x] v0.6 — Async PostgreSQL (SQLAlchemy), Redis rate limiting, OpenTelemetry APM, LLM integration tests
- [x] v1.0 — WebSocket drift alerts, Prometheus endpoint, multi-tenant RBAC, org management API
- [x] v1.1 — MCP server (10 tools, 5 resources), audit log API, red team API, billing API, Alembic migrations, per-org rate limiting, DB-persisted webhook retry queue
- [x] v1.2 — Public Leaderboard, Trust Index/Passports + embeddable badges, AI Incident Database, TOTP MFA, expanded field encryption, DB-persisted webhooks, full dashboard UI rebuild, white-label branding, a genuinely live hosted instance — see `CHANGELOG.md` for the full list
- [x] WhitePact migration (`1.2.0` → `1.2.2`) — governance decision core, MCP Streamable HTTP + OAuth/OIDC, risk tiering + policy engine, hash-chained evidence, approval workflow, multi-approver quorum + delegation chains, upstream MCP tool discovery, MCP trust/supply-chain scanner, HA Helm deployment, supply chain security (SBOM/provenance), release engineering, open source governance, live listings on the official MCP Registry and Smithery — see `MIGRATION_WHITEPACT_V2.md` for the full phase-by-phase log and what's still not done
- [ ] v2.0 onward — see `VERSION_ROADMAP.md` for the phase-by-phase plan through v6.0
- **Strategic direction** — `GAME_CHANGER_STRATEGY.md` lays out an infrastructure-first bet (free public trust registry, an agent-native trust-check primitive, AI-answer-engine citability) as an alternative to the enterprise-SaaS path, with `GAME_CHANGER_BUILD_PLAN.md` breaking it into concrete engineering phases against the current codebase

---

## Security & Open Source Assurance

The official [OpenSSF/OSPS BadgeApp project](https://www.bestpractices.dev/projects/14112)
currently records **OpenSSF Best Practices Silver** and **OSPS Baseline Level 1**.
They are voluntary project evidence, not an independent audit, penetration test, SOC 2,
or ISO certification. Current technical and claim boundaries are maintained in
[`WHITEPACT_TRUST_STATUS.md`](compliance/WHITEPACT_TRUST_STATUS.md) and
[`PUBLIC_TRUST_CLAIMS.md`](compliance/PUBLIC_TRUST_CLAIMS.md).

Release consumers can review the [signed-tag evidence](compliance/SIGNED_VERSION_TAGS.md),
[release process](RELEASING.md), [security policy](SECURITY.md),
[reproducible-build evidence](compliance/OPENSSF_SECURITY_EVIDENCE.md), and CycloneDX SBOM
attached to the named GitHub release. The separate SLSA hardening branch contains the
[SLSA evidence boundary](https://github.com/Guruprasath-Annadurai/Whitepact/blob/security/slsa-build-l3-hardening/compliance/SLSA_BUILD_PROVENANCE.md)
and [consumer verification guide](https://github.com/Guruprasath-Annadurai/Whitepact/blob/security/slsa-build-l3-hardening/docs/VERIFY_RELEASE.md);
Build L3 remains pending until a new release is produced through that architecture and
its exact artifacts are independently verified.

---

## Further reading

- [`SPEC.md`](SPEC.md) — the current architecture contract
- [`MACHINE_AUTHORITY_PROBLEM.md`](MACHINE_AUTHORITY_PROBLEM.md) — the problem the v3 authority-layer work answers
- [`MACHINE_AUTHORITY_V1.md`](MACHINE_AUTHORITY_V1.md) — inventory of the eight core machine-authority invariants (Delegation Graph, Autonomy Budget, Memory Firewall, Evidence Bundle, and more)
- [`ENFORCEMENT_BOUNDARY.md`](ENFORCEMENT_BOUNDARY.md) — precisely where each invariant's authority stops: inline enforcement vs. voluntary chokepoint
- [`LEGACY_TO_MACHINE_AUTHORITY_MAP.md`](LEGACY_TO_MACHINE_AUTHORITY_MAP.md) — mapping RBAC/OAuth/IAM concepts onto their WhitePact equivalents, for readers coming from traditional access control
- [`MIGRATION_WHITEPACT_V2.md`](MIGRATION_WHITEPACT_V2.md) — phase-by-phase migration log, what's done and what's explicitly not
- [`DEFINITION_OF_DONE.md`](DEFINITION_OF_DONE.md) — closing report: what's real today, what isn't, verifiable
- [`SECURITY_THREAT_MODEL.md`](SECURITY_THREAT_MODEL.md) — current security threat and attack-surface model
- [`DETERMINISTIC_VS_PROBABILISTIC.md`](DETERMINISTIC_VS_PROBABILISTIC.md) — why governance decisions are deterministic
- [`SLA.md`](SLA.md), [`ENTERPRISE_SECURITY.md`](ENTERPRISE_SECURITY.md), [`SECURITY.md`](SECURITY.md) — enterprise/security posture, stated honestly
- [`compliance/SOC2_ALTERNATIVE_PATH.md`](compliance/SOC2_ALTERNATIVE_PATH.md) — real, free, independently verifiable trust signals for now; the honest path to a real SOC 2 when there's budget for one
- [`docs/ACCESSIBILITY.md`](docs/ACCESSIBILITY.md), [`docs/INTERNATIONALIZATION.md`](docs/INTERNATIONALIZATION.md) — WCAG2AA accessibility approach and the dashboard's i18n architecture, both with real automated CI gates
- [`compliance/PROJECT_CONTINUITY_PLAN.md`](compliance/PROJECT_CONTINUITY_PLAN.md) — the access/recovery checklist a second person would need if the founder became unavailable; stated honestly as a plan, not proof of bus-factor redundancy (no second person holds this access yet)

---

## License

MIT — see [LICENSE](LICENSE).
