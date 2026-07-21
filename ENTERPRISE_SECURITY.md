# Enterprise Security Posture — ResponsibleAI Platform v1.2.0

This document answers the questions a security/procurement team asks before
approving a vendor. It states current fact, not aspiration — where a control
isn't implemented yet, that's said plainly rather than implied.

For vulnerability disclosure, see [SECURITY.md](SECURITY.md). For SLA/uptime
commitments, see [SLA.md](SLA.md).

---

## Encryption at rest

Encryption at rest is the deployer's responsibility, not something the
application layer provides on top of the database — this is standard for
self-hosted software and worth being explicit about:

| Database backend | Encryption at rest |
|---|---|
| SQLite (default, self-hosted) | **Not encrypted by the application.** The `.db` file is plaintext on disk unless the host filesystem/volume is encrypted (LUKS, dm-crypt, encrypted EBS/PD volume, FileVault, BitLocker, or — for the reference deployment on Oracle Cloud Infrastructure — [OCI Block Volume's default AES-256 encryption](https://docs.oracle.com/en-us/iaas/Content/Block/Concepts/blockvolumeencryption.htm), which applies with no configuration required). We recommend running SQLite only behind a full-disk-encrypted volume in production. |
| PostgreSQL (recommended for production, `RAI_DATABASE_URL`) | Encryption at rest depends on your Postgres provider. Managed services (AWS RDS, GCP Cloud SQL, Azure Database for PostgreSQL) encrypt storage by default. On the reference deployment (self-managed Postgres on OCI Always Free, via `docker-compose.prod.yml`), the underlying OCI Block Volume is encrypted at rest by default regardless — self-managed Postgres on other providers still requires disk-level encryption configured separately. |
| Redis (optional, rate limiting only) | Redis stores rate-limit counters, never governance data, PII, or credentials. Encryption at rest is not required for this use case but is unaffected by our config either way — follow your Redis provider's defaults. |

**What the application layer does guarantee regardless of disk encryption:**
- API keys are never stored in plaintext — only SHA-256 hashes (`org_api_keys.key_hash`). A raw key is shown exactly once at creation and cannot be recovered from the database.
- Stripe secrets, OIDC client secrets, and webhook HMAC secrets are read from environment variables, never written to the database.
- Webhook payloads are HMAC-SHA256 signed in transit (`X-RAI-Signature-256`), independent of storage encryption.

**Encryption in transit:** TLS termination is the deployer's responsibility (reverse proxy / load balancer / ingress). The application itself speaks plain HTTP — see `DEPLOYMENT.md` for the recommended nginx TLS config.

**Gap, stated honestly:** there is no field-level or transparent database encryption built into the application (no SQLCipher, no pgcrypto column encryption). For customers who require this as a hard requirement rather than infra-level disk encryption, this is not yet supported — flag it during evaluation rather than discovering it in production.

---

## Data residency

ResponsibleAI is self-hosted by default. **You control where your data lives** because you control the infrastructure — there is no ResponsibleAI-operated cloud region your data passes through unless you explicitly configure one (e.g. calling OpenAI/Anthropic/Google APIs from the cost-tracking or eval modules, which is opt-in per your own provider configuration).

| Deployment mode | Data location |
|---|---|
| Self-hosted (Docker / Helm / bare-metal) | Entirely within your infrastructure and region. No data leaves your network unless you configure outbound integrations (webhooks, LLM provider APIs, Stripe billing, OTLP telemetry export) — all of which are optional and explicitly configured. Reference/planned deployment: Oracle Cloud Infrastructure Always Free tier, single home region (see `compliance/CAIQ_SELF_ASSESSMENT.md` Domain 6 for exact region-selection and capacity considerations). |
| Hosted MCP (`responsibleai-mcp-http`), self-operated | Same as above — this is a transport option you run yourself, not a managed service we operate. |
| A future ResponsibleAI-operated SaaS tier | **Not yet available.** No such offering exists today. If/when one ships, this document will be updated with the specific region(s), sub-processor list, and data flow diagram before it's sold as a data-residency-compliant product. |

**Third-party data flows that exist only if you enable them:**
- LLM provider calls (OpenAI, Anthropic, Google, etc.) — your API keys, your account, your provider's data handling terms apply.
- Stripe (billing) — customer/subscription metadata only (see `billing/stripe_service.py`); no governance data is sent to Stripe.
- OTLP telemetry export — opt-in via `RAI_OTEL_ENDPOINT`; sends operational metrics/traces to your configured collector, not governance data.
- OIDC/SSO provider — authentication claims only, per your IdP configuration.

---

## Audit trail integrity

Every API request is logged to the `audit_log` table (endpoint, method, org, key, status, timing — never request/response bodies). As of v1.2.0, entries are **hash-chained**: each entry's hash is computed from its own fields plus the previous entry's hash (`entry_hash = sha256(prev_hash + fields)`), so any row edited or deleted directly against the database breaks the chain at that point.

- Verify integrity: `GET /api/audit/verify` (super-admin only) recomputes the chain and reports the first broken link, if any.
- Export for SIEM/compliance evidence: `GET /api/audit/export` (CSV, includes `entry_hash`/`prev_hash`) or `GET /api/audit` (JSON).
- Retention: configurable via `AuditRepository.cleanup(retention_days=N)`; not run automatically — schedule it per your compliance retention policy.

**Stated honestly — what this does and doesn't protect against:**
- Detects: accidental or malicious row edits/deletes made directly against the database outside the application (the common tamper scenario auditors ask about).
- Does not detect: an attacker with full database write access recomputing the entire chain from scratch. No hash chain without external anchoring (e.g. periodic publication to write-once storage) can defend against that — we don't claim otherwise.
- Chain scope: process-local. Each server replica maintains its own chain over its own writes; this is not a single global chain across a multi-replica deployment. Verification reports on whichever database it's pointed at.

---

## SSO / authentication

- **OIDC (OAuth2 Authorization Code flow)** is supported — configure `RAI_OIDC_ISSUER`, `RAI_OIDC_CLIENT_ID`, `RAI_OIDC_CLIENT_SECRET`. Login: `GET /api/auth/login/oidc`, callback: `GET /api/auth/callback`.
- **SSO enforcement**: an org can require SSO-only login via `PUT /api/orgs/{id}/sso {"sso_required": true}` (OWNER role). Once enabled, that org's static API keys stop authenticating — every request must present a valid OIDC-issued Bearer token. This closes the common gap where a departed employee's static API key remains a valid backdoor after SSO rollout.
- **SAML is not supported.** If your identity provider requires SAML 2.0 specifically (rather than OIDC, which most modern IdPs — Okta, Azure AD, Google Workspace — support as an alternative), this is a gap today, not a documented-but-untested feature. Ask before assuming it works.

---

## RBAC

Four roles, strictly hierarchical: `OWNER > ADMIN > ANALYST > VIEWER`. Every endpoint declares its minimum required role via `require_role(...)`. Org-scoped API keys can only act within their own org; only legacy super-admin keys (flat `RAI_API_KEYS`, not tied to an org) can act across orgs — and that cross-org capability is itself logged in the audit trail per request.

---

## Multi-tenancy isolation

All governance data (trust scores, cost/token usage, audit log, MCP tool call metering) carries an `org_id` column and every repository method filters by it. Cross-org data leakage is a defect if found — file it under `SECURITY.md`'s scope, not a feature request.

---

## What's not covered here

- SOC2 / ISO 27001 certification status — see `SLA.md` and ask directly; certification is a roadmap item, not a current claim.
- Penetration test reports — request current status directly; not published in this repo.
- A signed Data Processing Agreement — a draft template with the current sub-processor list (OCI, Stripe, customer's own OIDC/LLM choices) exists at `compliance/DPA_TEMPLATE.md`, explicitly marked as unreviewed by counsel; not something to treat as an executable contract yet.

This document is updated alongside the platform. If you find a claim here that's stale relative to the code, treat the code as ground truth and report the discrepancy per `SECURITY.md`.
