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

## Sub-processors

| Sub-processor | Purpose | Certifications |
|---|---|---|
| Render | Compute hosting for the live reference deployment (`responsibleai-dashboard`), building and running the Docker image on every push to `main` — the actual currently-running instance as of 2026-07-23; see `compliance/CAIQ_SELF_ASSESSMENT.md` Domain 6 | SOC 2 Type II compliant, ISO/IEC 27001 certified — see [render.com/docs/certifications-compliance](https://render.com/docs/certifications-compliance) |
| Supabase | Managed PostgreSQL for the live reference deployment, accessed via its transaction-pooler endpoint | SOC 2 Type II, ISO 27001, HIPAA, PCI DSS certified — see [supabase.com/docs/guides/security/soc-2-compliance](https://supabase.com/docs/guides/security/soc-2-compliance) |
| Upstash | Managed Redis for the live reference deployment's rate-limit backend | No independently verified certification found as of this review — stated honestly rather than assumed; re-check before citing this vendor in a customer-facing security review |
| Stripe, Inc. | Payment processing and subscription billing (PRO/ENTERPRISE plans only) — no governance data reaches Stripe, billing metadata only | Stripe's own published PCI-DSS Level 1 certification |
| Customer's own OIDC/SSO provider (if enabled) | Authentication only | Per the customer's own IdP choice — not selected or certified by us |
| LLM providers (OpenAI, Anthropic, Google, etc.), if configured | Model evaluation and cost tracking, under the customer's own account and API keys | Per each provider's own terms |

Full detail, including exactly what each sub-processor does and doesn't
receive, is in `compliance/DPA_TEMPLATE.md`'s Section 2 — this table is a
summary, that document is the source of truth. Sub-processor changes will
be reflected here and in the DPA template together, not one without the
other.

---

## Disaster recovery

Applies to the Postgres-backed hosted stack (`docker-compose.prod.yml`).
Self-hosted SQLite deployments are the customer's own backup responsibility —
`scripts/backup-postgres.sh` is Postgres-specific.

| Tier | RPO (data loss window) | RTO (time to restore) |
|---|---|---|
| PRO | 24 hours (nightly backup) | 4 hours |
| ENTERPRISE | 24 hours (nightly backup); contact for point-in-time recovery | 1 hour |

**Backup**: `scripts/backup-postgres.sh` — `pg_dump`, gzip-compressed, 30-day
local retention by default. Intended to run nightly via cron; ship the
output off-host (S3, rsync, etc.) for real disaster recovery — a backup
that lives on the same disk as the database it backs up doesn't protect
against disk/host failure, only against bad migrations or accidental
deletes.

**Restore**: `scripts/restore-postgres.sh <backup_file>` — drops and
recreates the target database from a `pg_dump` file, with an explicit
type-to-confirm prompt since it's destructive.

**Stated honestly**: nightly `pg_dump` gives a 24h RPO, not continuous
replication. If your compliance requirements need a tighter RPO
(point-in-time recovery, streaming replication to a standby), that's not
implemented yet — say so during evaluation rather than assuming it from
the ENTERPRISE tier name.

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

**Note on the reference deployment (Render free tier + Supabase managed
Postgres + Upstash managed Redis — updated 2026-07-23):** the live
instance runs on Render's free web-service tier (shared CPU, no
persistent local disk — this is exactly why Postgres lives on Supabase
rather than in-container SQLite), which falls well below the
"Recommended" column's 4+ vCPUs per replica. This is a managed-services
architecture, not a single VM, so "Deployment" above (`docker-compose.prod.yml`)
describes the *self-hosted VM alternative* in `DEPLOY_RUNBOOK.md`, not
the actual live topology. Workable for early-stage/low-traffic use; treat
"Recommended" as the bar to grow into with paid capacity on any of these
three providers, not a claim about the current reference setup.

**Running more than one replica:** set `RAI_MULTI_REPLICA=true`. This is a
self-declaration, not a feature flag — it makes startup verify the
database and rate-limit backends can actually be shared across replicas
(Postgres + Redis) and log a loud warning if not, instead of silently
running with per-replica state that makes rate limits and (for SQLite)
data integrity wrong in ways that don't show up until real multi-replica
traffic hits. See `DEPLOY_RUNBOOK.md` §13b for what this platform does and
does not provide toward multi-region/HA — no multi-region active-active
topology exists in this repo; that remains infrastructure the deployer
builds.

---

## Versioning & backward compatibility

- The API follows semantic versioning (MAJOR.MINOR.PATCH).
- Minor and patch releases are backward-compatible.
- Breaking changes in major releases are announced via GitHub releases with a minimum 60-day migration window.
- The `/api/openapi.json` schema is the authoritative contract for all endpoints.

---

*Last updated: 2026-07-21 — ResponsibleAI v1.2.0*
