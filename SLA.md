# Service Level Agreement — ResponsibleAI Platform v1.2.0

## Scope

This SLA covers the ResponsibleAI Governance Platform API, Governance Dashboard,
and hosted MCP endpoint. Tier names match the billing plans in `mcp/licensing.py`
and `GET /api/v1/billing/plans` — FREE, PRO, ENTERPRISE — rather than a separate
naming scheme, so what you see in billing is what this SLA refers to.

**Self-hosted (FREE)**: you operate the infrastructure; targets below are
recommendations for what to design toward, not a commitment we can enforce
on infrastructure we don't control.

**Hosted (PRO/ENTERPRISE)**: as of v1.2.0, no ResponsibleAI-operated hosted
instance is live yet — `docker-compose.prod.yml` is the production-ready
stack (Postgres + Redis, not SQLite/in-memory limiting) for standing one up.
Once a hosted instance is running against this stack, these targets become
an enforceable commitment for that instance specifically.

---

## Uptime tiers

| Tier | Target SLA | Recommended use |
|---|---|---|
| **FREE** (self-hosted) | 99.0% monthly (design target, not enforced) | Internal tooling, non-critical governance pipelines |
| **PRO** (hosted) | 99.5% monthly | Pre-production model evaluation gates |
| **ENTERPRISE** (hosted) | 99.9% monthly | Production inference guardrails, compliance logging |

Uptime is measured as `(total_minutes - downtime_minutes) / total_minutes × 100`.
Scheduled maintenance windows (max 4 hours/month, announced 48h in advance) are excluded.

---

## Response time targets (p95, same-region)

| Endpoint | FREE | PRO | ENTERPRISE |
|---|---|---|---|
| `/api/health` | < 50ms | < 20ms | < 10ms |
| `/api/evaluate` | < 500ms | < 300ms | < 150ms |
| `/api/scan` | < 200ms | < 100ms | < 50ms |
| `/api/hallucination` | < 300ms | < 150ms | < 80ms |
| `/api/cost/analyze` | < 200ms | < 100ms | < 50ms |
| `/api/cost/route` | < 100ms | < 50ms | < 25ms |

---

## Incident classification

| Severity | Definition | Initial response | Resolution target |
|---|---|---|---|
| **P1 — Critical** | API down, data loss risk, security breach | 1 hour | 4 hours |
| **P2 — High** | Core endpoint errors (≥5% error rate), auth failures | 4 hours | 24 hours |
| **P3 — Medium** | Performance degradation, non-critical endpoint failures | 1 business day | 3 business days |
| **P4 — Low** | Cosmetic issues, documentation gaps | 3 business days | 2 weeks |

---

## Data retention

| Data type | Default retention | Configurable |
|---|---|---|
| Trust score history | 365 days | Yes — delete rows from `trust_scores` |
| Token usage records | 365 days | Yes — delete rows from `token_usage` |
| Application logs | 30 days (stdout) | Yes — pipe to log aggregator |

---

## Security commitments

- All API keys are stored in memory only; never written to database or logs.
- PII detected by the Guardrails Engine is redacted in all log output.
- Request bodies are limited to 10 MB by default.
- HTTPS is enforced when deployed behind the recommended reverse proxy.
- Security vulnerabilities can be reported to: milchcreamfoods@gmail.com
  See [SECURITY.md](SECURITY.md) for the full responsible disclosure policy.

---

## Support tiers

| Tier | Channels | Response time | Included |
|---|---|---|---|
| **FREE** | GitHub Issues, email | Next business day | All licenses |
| **PRO** | GitHub Issues, email, Slack | 4 business hours | PRO plan |
| **ENTERPRISE** | All channels + dedicated TAM + phone | 1 hour (24/7) | ENTERPRISE plan |

### Support contacts

| Channel | Address |
|---|---|
| GitHub Issues | https://github.com/Guruprasath-Annadurai/ResponsibleAi/issues |
| Email | milchcreamfoods@gmail.com |
| Status API | `GET /api/support/status` — public, no auth, real-time platform status |
| Public status page | See "Uptime status page" below — not yet live |
| SLA tiers API | `GET /api/support` — full tier details and contact info |
| MCP usage (this org) | `GET /api/v1/billing/usage/mcp` — current billing-period call volume |
| Billing plans | `GET /api/v1/billing/plans` — tools and pricing per tier |

---

## Uptime status page

**Honest current state**: no public status page is live yet. `GET /api/health`
and `GET /api/support` exist today and can be polled directly or wired into
any external status-page tool (UptimeRobot, Better Uptime, statuspage.io) —
that account setup is an operational step, not something the application
ships with. This section will link the live page once one exists; until
then, treat its absence as a known gap, not an oversight.

---

## Exclusions

This SLA does not cover:
- Downtime caused by the customer's infrastructure (cloud provider outages, networking).
- Degraded performance due to undersized hardware (see minimum requirements below).
- Failures caused by modifications to the platform source code by the customer.
- Third-party LLM provider outages affecting model evaluation accuracy.

---

## Minimum hardware requirements

| Component | Minimum (SQLite, single instance) | Recommended (Postgres + Redis, hosted) |
|---|---|---|
| CPU | 2 vCPUs | 4+ vCPUs per replica |
| RAM | 512 MB | 2 GB per replica |
| Storage | 1 GB | 20 GB+ (Postgres volume, grows with audit/usage history) |
| Python | 3.11+ | 3.12 |
| OS | Linux (amd64/arm64) | Ubuntu 22.04 LTS |
| Deployment | `docker-compose.yml` | `docker-compose.prod.yml` (Postgres + Redis + dashboard + MCP HTTP) |

---

## Versioning & backward compatibility

- The API follows semantic versioning (MAJOR.MINOR.PATCH).
- Minor and patch releases are backward-compatible.
- Breaking changes in major releases are announced via GitHub releases with a minimum 60-day migration window.
- The `/api/openapi.json` schema is the authoritative contract for all endpoints.

---

*Last updated: 2026-07-12 — ResponsibleAI v1.2.0*
