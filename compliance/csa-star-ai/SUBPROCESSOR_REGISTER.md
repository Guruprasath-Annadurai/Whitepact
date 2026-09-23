# Subprocessor / vendor register (2026-09-23)

**Scope:** WhitePact-hosted SaaS reference architecture. Self-hosted customers substitute their own infrastructure; this register describes vendors WhitePact may rely on when operating a hosted tier.

| Vendor | Purpose | Data involved | Access | Criticality | Contract/DPA | Security evidence | Fallback | Last review |
|--------|---------|---------------|--------|-------------|--------------|-------------------|----------|-------------|
| **Hosting provider** (e.g. Render, Fly.io, or customer VPS) | Application runtime | All tenant governance data at rest in configured Postgres | Infrastructure admin | Critical | Customer MSA + DPA | **OWNER:** OA-002 provider export | Redeploy to alternate region/provider | 2026-09-23 — **provider evidence pending** |
| **Managed PostgreSQL** | Primary datastore | Tenant configs, audit logs, authority records | DB credentials | Critical | Subprocessor DPA | Provider SOC2/ISO (owner verify) | Restore from backup | 2026-09-23 |
| **Managed Redis** (optional) | Rate limits, authority kernel reservations | Ephemeral tokens, counters | Network + AUTH | High | Subprocessor DPA | Provider docs | Degrade to fail-closed paths in code | 2026-09-23 |
| **Paddle, Inc.** | Subscription billing (production path: `paddle_service.py`) | Billing contact, subscription metadata — **not** governance payloads | API key | Medium | Paddle DPA | Paddle published compliance | Billing UI unavailable; core governance continues | 2026-09-23 |
| **GitHub, Inc.** | Source control, CI, Dependabot | Source code, secrets in Actions (must use secrets store) | Repo admin | High | GitHub DPA | GitHub SOC reports | Mirror + alternate forge | 2026-09-23 |
| **Customer IdP** (OIDC/SAML) | Enterprise SSO | Identity assertions per customer config | Customer-controlled | High | Customer contract | Customer evidence | Local auth fallback if configured | Continuous (customer) |
| **Customer LLM provider** | Upstream model calls via customer integration | Prompts/outputs per customer policy | Customer API keys | High | Customer contract | Customer evidence | N/A — customer choice | Continuous (customer) |

### Deprecated / legacy references

- **Stripe:** Legacy module `billing/stripe_service.py` may remain for migration; **production checkout on branch `acddae1` uses Paddle** (`paddle_service.py`, Paddle.js on web). Do not list Stripe as primary billing subprocessor in new submissions without verifying live configuration.

### Review cadence

Quarterly review by Founder / Security Owner; update this file and `compliance/VENDOR_RISK_ASSESSMENT.md` together.
