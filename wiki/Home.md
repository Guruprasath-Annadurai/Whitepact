# ResponsibleAI Wiki

**The Trust Layer for AI — Enterprise Governance Platform**

---

ResponsibleAI is an open-source AI governance platform that provides trust scoring, bias detection, guardrails, hallucination detection, compliance auditing, cost intelligence, drift monitoring, and an MCP server for Claude Code integration.

## Quick navigation

| Section | Description |
|---|---|
| [Architecture](Architecture) | System design, module map, data flow |
| [Getting Started](Getting-Started) | Install, first run, 5-minute quickstart |
| [API Reference](API-Reference) | All REST endpoints with request/response examples |
| [MCP Server](MCP-Server) | Claude Code integration — tools, resources, setup |
| [Configuration](Configuration) | All environment variables and their effects |
| [Database & Migrations](Database-and-Migrations) | SQLite, PostgreSQL, Alembic usage |
| [Authentication & RBAC](Authentication-and-RBAC) | Bearer tokens, roles, org management |
| [Webhooks](Webhooks) | Event delivery, HMAC signing, retry persistence |
| [BiasBuster](BiasBuster) | Bias probes, scoring methodology, CI gate |
| [PrivacyLabel](PrivacyLabel) | Federated learning, differential privacy |
| [Compliance Frameworks](Compliance-Frameworks) | NIST AI RMF, EU AI Act, ISO 42001 |
| [Deployment](Deployment) | Docker, Kubernetes, Helm, PostgreSQL+Redis |
| [Contributing](Contributing) | Dev setup, test suite, code style |
| [Roadmap](Roadmap) | What's shipped, what's next |

---

## Platform at a glance

```
┌─────────────────────────────────────────────────────────────────┐
│                    ResponsibleAI v1.1.0                         │
│                                                                 │
│  Claude Code ──► MCP Server (10 tools, 5 resources)            │
│                       │                                         │
│  REST Client ─────────┤                                         │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Governance Dashboard (FastAPI)              │   │
│  │  Auth · Per-org rate limit · Audit log · OTEL · WS      │   │
│  └──────────────────────────────────────────────────────────┘   │
│       │          │          │          │          │              │
│  Trust      Compliance  Guardrails  Cost     Red Team           │
│  Score      NIST/EU/ISO  PII+Tox  Tracking  Simulator          │
│       │          │          │          │          │              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         SQLAlchemy (SQLite / PostgreSQL)                 │   │
│  │         Alembic migrations · WAL mode · async           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Repository structure

```
src/
├── responsibleai/          # Core governance engine + dashboard
│   ├── dashboard/          # FastAPI app, routes, WebSocket, static SPA
│   ├── db/                 # Async SQLAlchemy engine, repositories
│   ├── trust/              # TrustScoreEngine (6-dim, A–F grade)
│   ├── compliance/         # NIST AI RMF, EU AI Act, ISO 42001
│   ├── guardrails/         # PII detection, toxicity filtering
│   ├── hallucination/      # TF-IDF self-consistency + hedging analysis
│   ├── redteam/            # 10 adversarial attack vectors
│   ├── cost/               # Token tracking, model routing, budget alerts
│   ├── mcp/                # MCP server (stdio, 10 tools, 5 resources)
│   ├── webhooks/           # HMAC-signed event delivery + DB retry queue
│   ├── rbac/               # OWNER/ADMIN/ANALYST/VIEWER roles
│   └── auth/               # Bearer token + OIDC/JWKS validation
├── biasbuster/             # Bias evaluation CLI + 6 demographic probes
└── privacylabel/           # Federated learning + differential privacy
migrations/                 # Alembic versioned schema
tests/                      # 942 tests
```
