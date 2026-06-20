# Service Level Agreement — ResponsibleAI Platform v0.5.0

## Scope

This SLA covers the ResponsibleAI Governance Platform API and Governance Dashboard
when self-hosted by the customer on infrastructure they control.

---

## Uptime tiers

| Tier | Target SLA | Recommended use |
|---|---|---|
| **Standard** | 99.0% monthly | Internal tooling, non-critical governance pipelines |
| **Professional** | 99.5% monthly | Pre-production model evaluation gates |
| **Enterprise** | 99.9% monthly | Production inference guardrails, compliance logging |

Uptime is measured as `(total_minutes - downtime_minutes) / total_minutes × 100`.
Scheduled maintenance windows (max 4 hours/month, announced 48h in advance) are excluded.

---

## Response time targets (p95, same-region)

| Endpoint | Standard | Professional | Enterprise |
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

## Support channels

| Channel | Availability | Scope |
|---|---|---|
| GitHub Issues | Community hours | Bug reports, feature requests |
| Email (milchcreamfoods@gmail.com) | 2 business days | Enterprise integration support |

---

## Exclusions

This SLA does not cover:
- Downtime caused by the customer's infrastructure (cloud provider outages, networking).
- Degraded performance due to undersized hardware (see minimum requirements below).
- Failures caused by modifications to the platform source code by the customer.
- Third-party LLM provider outages affecting model evaluation accuracy.

---

## Minimum hardware requirements

| Component | Minimum | Recommended |
|---|---|---|
| CPU | 2 vCPUs | 4 vCPUs |
| RAM | 512 MB | 2 GB |
| Storage | 1 GB | 20 GB (for SQLite growth) |
| Python | 3.11+ | 3.12 |
| OS | Linux (amd64/arm64) | Ubuntu 22.04 LTS |

---

## Versioning & backward compatibility

- The API follows semantic versioning (MAJOR.MINOR.PATCH).
- Minor and patch releases are backward-compatible.
- Breaking changes in major releases are announced via GitHub releases with a minimum 60-day migration window.
- The `/api/openapi.json` schema is the authoritative contract for all endpoints.

---

*Last updated: 2025-06-20 — ResponsibleAI v0.5.0*
