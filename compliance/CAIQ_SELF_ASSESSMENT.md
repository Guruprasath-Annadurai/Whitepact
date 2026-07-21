# Consensus Assessment Self-Assessment — ResponsibleAI Platform v1.2.0

Modeled on the Cloud Security Alliance's Consensus Assessment Initiative
Questionnaire (CAIQ) domain structure. This is our own self-administered
response, not a copy of CSA's proprietary question text, and not a
substitute for a formal SOC2/ISO 27001 audit — it exists so a security
reviewer doesn't have to wait on one to get real answers.

**How to use this:** every answer states current fact and cites the exact
file/mechanism behind it. Where a control doesn't exist, that's stated
plainly, not omitted. If you find a claim here that doesn't match the code,
the code is ground truth — report the discrepancy per `SECURITY.md`.

Last reviewed: 2026-07-21 · Platform version: 1.2.0

---

## Domain 1 — Application & Interface Security

| Question | Answer |
|---|---|
| Are applications tested for security vulnerabilities before release? | Automated: ruff and mypy (strict-optional, zero suppressed errors) gate every commit via CI. `pip-audit` scans every dependency on every CI run as of this review — one known finding to date (nltk path traversal, PYSEC-2026-597), triaged as non-exploitable in this codebase's actual usage and tracked pending an upstream fix; see Domain 15. Manual third-party pentest: not yet performed (see Domain 16). |
| Is input validation enforced on all external-facing APIs? | Yes — every REST endpoint uses Pydantic request models with explicit field constraints (`min_length`, `max_length`, `pattern`, `ge`/`le`). See `dashboard/app.py` request model definitions. |
| Are API keys/secrets ever exposed in logs or error messages? | No — API keys are stored as SHA-256 hashes only (`org_api_keys.key_hash`); raw keys are shown exactly once at creation. Stripe/OIDC/webhook secrets are read from environment variables, never logged or persisted to the database. |
| Is output encoding applied to prevent injection attacks? | SQL: parameterized queries throughout via SQLAlchemy Core (`db/*.py`) — no raw string interpolation into SQL. XSS: the platform is API-first with no server-rendered HTML from user input; the dashboard's static assets are pre-built, not templated with request data. |
| Are session tokens/API keys rotated and revocable? | Yes — `DELETE /api/orgs/{id}/keys/{key_id}` revokes immediately (checked on every `authenticate()` call, not cached). No automatic rotation policy is enforced by the platform; that's an operational practice for the deployer. |

---

## Domain 2 — Audit Assurance & Compliance

| Question | Answer |
|---|---|
| Is there an immutable or tamper-evident audit trail? | Yes, as of v1.2.0 — the `audit_log` table is hash-chained (`entry_hash = sha256(prev_hash + fields)`). `GET /api/audit/verify` recomputes the chain and reports the first broken link. See `ENTERPRISE_SECURITY.md`'s Audit Trail Integrity section for exact scope and limitations — it detects direct DB tampering, not a fully compromised database with write access. |
| Can audit logs be exported for external SIEM ingestion? | Yes — `GET /api/audit/export` (CSV, includes hash-chain fields) and `GET /api/audit` (JSON). |
| Is there a third-party compliance certification (SOC2, ISO 27001)? | **No.** Not yet started. This questionnaire, the Trust Center page, and the NIST CSF self-assessment are the current substitutes while that roadmap item is pending funding. See "Compliance roadmap" at the end of this document. |
| Are compliance framework mappings available (NIST AI RMF, EU AI Act, ISO 42001)? | Yes, but for the AI governance product surface, not the platform's own infosec posture — `rai_compliance`, `rai_eu_ai_act_classify`, `rai_iso42001_gap` MCP tools and `GET /api/v1/billing/plans`-adjacent compliance endpoints implement these. Don't conflate AI-governance-framework support (a product feature) with the platform's own security certification status (not yet obtained). |

---

## Domain 3 — Business Continuity Management & Operational Resilience

| Question | Answer |
|---|---|
| Is there a documented disaster recovery plan? | Yes — `SLA.md`'s "Disaster recovery" section. RPO 24h (nightly `pg_dump`), RTO 1-4h depending on tier. `scripts/backup-postgres.sh` / `scripts/restore-postgres.sh`. |
| Is backup data encrypted? | Backup files are not encrypted by the script itself — encrypt at the storage layer (S3 SSE, encrypted volume) where you ship them, per `ENTERPRISE_SECURITY.md`'s encryption-at-rest posture. |
| Is there a documented uptime SLA? | Yes — `SLA.md`, tiered by plan (FREE 99.0% design target/not enforced, PRO 99.5%, ENTERPRISE 99.9%). |
| Is there redundancy/failover for the hosted stack? | `docker-compose.prod.yml` runs single-instance dashboard + MCP services against Postgres/Redis — no automatic failover between replicas is configured today. Multi-replica horizontal scaling is supported (Helm chart, HPA) but automatic failover orchestration is the deployer's Kubernetes/cloud provider responsibility, not built into the app. |

---

## Domain 4 — Change Control & Configuration Management

| Question | Answer |
|---|---|
| Are schema changes version-controlled and auditable? | Yes — Alembic migrations (`migrations/versions/`), auto-applied at startup as of v1.2.0 (`db/migrate.py`), fatal-on-failure rather than silently degrading. |
| Is there a rollback procedure for failed deployments? | Helm: standard `helm rollback`. Docker Compose: re-tag and redeploy previous image; database rollback via Alembic `downgrade` is supported per-migration but not automated. |
| Are production deployments gated by automated tests? | Yes — CI runs the full test suite (1000+ tests), mypy strict-optional, and `helm lint` before merge. |

---

## Domain 5 — Data Security & Information Lifecycle Management

| Question | Answer |
|---|---|
| Is data encrypted at rest? | See `ENTERPRISE_SECURITY.md` — deployer's responsibility (disk/volume encryption), not enforced by the application layer. Stated as a gap, not implied as covered. |
| Is data encrypted in transit? | TLS is the deployer's responsibility (reverse proxy termination) — the app speaks plain HTTP internally. See `DEPLOYMENT.md`'s nginx config. Webhook payloads carry HMAC-SHA256 signatures independent of transport encryption. |
| Is there a data retention and deletion policy? | Yes — configurable per data type (`SLA.md`'s Data Retention table): trust scores/token usage default 365 days, audit log via `AuditRepository.cleanup(retention_days=N)`. Not run automatically; scheduling is the deployer's responsibility. |
| Is PII detected and handled specially? | Yes — the Guardrails Engine (`rai_scan` / `GET /api/scan`) detects email, phone, SSN, credit card, IP address and can redact in real time; `rai_pii_report` aggregates findings for GDPR/CCPA evidence. |
| Is multi-tenant data isolated? | Yes — every governance data table (`trust_scores`, `token_usage`, `audit_log`, `mcp_tool_calls`) carries `org_id` and every repository method filters by it. Cross-org leakage is treated as a security defect, not a feature gap. |

---

## Domain 6 — Datacenter Security

| Question | Answer |
|---|---|
| Where is data physically hosted? | Self-hosted by default — **you** choose the datacenter/region, since you run the infrastructure. No ResponsibleAI-operated datacenter exists as of v1.2.0. See `ENTERPRISE_SECURITY.md`'s Data Residency section. |
| Is physical security independently certified? | Not applicable today — inherits whatever your chosen cloud/datacenter provider (AWS, GCP, Azure, on-prem) already has certified (their SOC2/ISO 27001 covers physical security, not ours). |

---

## Domain 7 — Encryption & Key Management

| Question | Answer |
|---|---|
| How are API keys/secrets stored? | API keys: SHA-256 hash only, never the raw value (`secrets.token_urlsafe(32)` generation, `hashlib.sha256` storage). Third-party secrets (Stripe, OIDC, webhook HMAC): environment variables only, never written to the database. |
| Is there a key rotation mechanism? | Manual — revoke + reissue via the API. No automatic rotation schedule enforced by the platform. |
| Is field-level/column-level encryption used for sensitive data? | No — this is an explicitly stated gap in `ENTERPRISE_SECURITY.md`. No SQLCipher, no pgcrypto column encryption. Relies on infra-level disk encryption instead. |

---

## Domain 8 — Governance and Risk Management

| Question | Answer |
|---|---|
| Is there a documented security policy? | Yes — `SECURITY.md` (vulnerability disclosure), `ENTERPRISE_SECURITY.md` (controls posture), this document (self-assessment). |
| Is there a formal risk assessment process? | Informal — no dedicated GRC tooling or scheduled risk review cadence yet. This is a real gap for a solo-maintained project; flagged honestly rather than fabricating a review cadence that doesn't happen. |
| Is there a named security contact? | Yes — `milchcreamfoods@gmail.com`, documented in `SECURITY.md` with a 48-hour acknowledgment commitment. |

---

## Domain 9 — Human Resources Security

| Question | Answer |
|---|---|
| Are background checks performed on personnel with data access? | Not applicable at current team size (solo maintainer). This will need a real answer once there's a team with production data access — flagged as forward-looking, not glossed over. |
| Is there security awareness training? | Not formalized — solo-maintained project. |

---

## Domain 10 — Identity & Access Management

| Question | Answer |
|---|---|
| Is role-based access control (RBAC) implemented? | Yes — four strictly hierarchical roles (`OWNER > ADMIN > ANALYST > VIEWER`), enforced via `require_role()` on every endpoint. |
| Is SSO supported? | OIDC (OAuth2 Authorization Code flow) — yes. SAML — no, explicitly not supported (see `ENTERPRISE_SECURITY.md`). |
| Can SSO be enforced (blocking password/API-key fallback)? | Yes — `PUT /api/orgs/{id}/sso` disables static API-key auth for that org once SSO is configured, closing the departed-employee-static-key backdoor. |
| Is least-privilege access enforced for cross-tenant operations? | Yes — org-scoped keys can only act within their own org; only legacy super-admin flat keys can cross org boundaries, and every such action is itself logged in the audit trail. |
| Is multi-factor authentication (MFA) supported? | Not directly by the platform — MFA is delegated to your OIDC identity provider (Okta, Azure AD, etc.), which is where MFA enforcement actually belongs for SSO-based auth. Static API-key auth has no MFA concept (it's a bearer secret, not a login). |

---

## Domain 11 — Infrastructure & Virtualization Security

| Question | Answer |
|---|---|
| Is the container image hardened? | Yes — runs as non-root (`appuser`, UID 1001), minimal base image (`python:3.12-slim`), no unnecessary packages beyond `curl` for healthchecks. |
| Are Kubernetes deployments hardened? | Yes — Helm chart sets `runAsNonRoot`, drops all capabilities, `readOnlyRootFilesystem` where applicable, PodDisruptionBudget (`minAvailable: 1`), explicit rolling-update strategy (`maxUnavailable: 0`) to prevent capacity drops during deploys. |
| Are database/cache ports exposed publicly? | No, by default in the reference `docker-compose.prod.yml` — Postgres and Redis run on an `internal: true` Docker network, unreachable from outside the compose stack. |

---

## Domain 12 — Interoperability & Portability

| Question | Answer |
|---|---|
| Can customer data be exported? | Yes — audit logs (`GET /api/audit/export`, CSV/JSON), cost/usage data via billing endpoints, trust score history via `GET /api/trust/history`. No proprietary lock-in format; all exports are standard CSV/JSON. |
| Is the platform open source? | Yes — MIT licensed, full source available. This is itself a portability/exit-risk mitigant: no vendor lock-in even if the vendor (solo maintainer) disappears. |

---

## Domain 13 — Mobile Security

| Question | Answer |
|---|---|
| Does the platform have a mobile app? | No — API-first, web dashboard only. Not applicable. |

---

## Domain 14 — Security Incident Management, E-Discovery & Cloud Forensics

| Question | Answer |
|---|---|
| Is there a documented incident response process? | Partial — `SECURITY.md` covers vulnerability disclosure response (48h ack, 7-day resolution timeline target). A dedicated internal incident-response runbook (detection → containment → notification) is not yet separately documented — real gap, noted here rather than implied as covered. |
| Can security incidents be logged in a structured, exportable format? | Yes — `rai_incident_log` MCP tool produces structured incident records with SIEM-ready payloads (severity, SLA resolution targets, evidence hashing). |
| Is there a customer notification process for breaches? | Not formally documented as a standalone breach-notification SLA. This should be built before any contract requiring formal breach notification timelines (e.g., 72-hour GDPR notification) is signed — flagged as a pre-contract gap, not assumed handled. |

---

## Domain 15 — Supply Chain Management, Transparency & Accountability

| Question | Answer |
|---|---|
| Is there a sub-processor list? | For self-hosted deployments: not applicable (you choose your own sub-processors — cloud provider, LLM providers, Stripe if you enable billing). For a future ResponsibleAI-operated hosted tier: doesn't exist yet, since no such tier is live. Will be published before one is sold. |
| Are third-party dependencies tracked and scanned? | Dependencies are declared in `pyproject.toml` with version constraints. `pip-audit` runs on every CI build (`.github/workflows/ci.yml`) and scans the full resolved dependency tree. One known vulnerability is currently tracked: `nltk` PYSEC-2026-597 (path traversal in `nltk.data.load()`/`find()` via percent-encoded traversal sequences) — reviewed and confirmed non-exploitable here, since this codebase's only nltk call passes a hardcoded literal resource name (`vader_lexicon`), never attacker-controlled input. Explicitly ignored in CI with that rationale documented inline, not silently suppressed. Dependabot is not configured (no automatic PR-based update flow yet — real remaining gap). |
| Is there an SBOM (Software Bill of Materials)? | Not yet generated. Given the project is open source with a fully inspectable dependency tree, this is lower priority than for closed-source vendors, but still a gap for buyers who require a formal SBOM artifact. |

---

## Domain 16 — Threat and Vulnerability Management

| Question | Answer |
|---|---|
| Has the platform undergone a third-party penetration test? | **No.** Not yet performed — cost-gated, same as SOC2. See `scripts/security-scan.sh` for a free automated OWASP ZAP baseline scan as an interim measure; explicitly not equivalent to a paid third-party pentest and not represented as one. |
| Is there a red-team / adversarial testing capability? | Yes, as a product feature — `rai_redteam_payloads` / `rai_redteam_analyze` MCP tools simulate prompt injection, jailbreak, data leakage, role confusion, and delimiter attacks against AI models under evaluation. This tests *models the platform evaluates*, not the platform's own infrastructure — don't conflate the two. |
| Is there a vulnerability disclosure program? | Yes — `SECURITY.md`, email-based, 48-hour acknowledgment, no bug bounty program (unfunded). |

---

## Domain 17 — Web Application Security (WAF/Perimeter)

| Question | Answer |
|---|---|
| Is there a Web Application Firewall in front of the platform? | Not provided by the platform — deployer's responsibility (Cloudflare, AWS WAF, nginx ModSecurity, etc.), same as TLS termination. |
| Is rate limiting enforced? | Yes, two independent layers: a flat per-route ceiling (protects the server itself, `slowapi`/`limits`) and a per-org plan-scaled budget (`PlanRateLimiter` — FREE 60/min, PRO 300/min, ENTERPRISE unlimited), Redis-backed when configured. |
| Are security headers set (CSP, HSTS, X-Frame-Options)? | Partially. `SecurityHeadersMiddleware` sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy: strict-origin-when-cross-origin`, `Cache-Control: no-store`, and `Permissions-Policy` on every response. **CSP and HSTS are not set by the application** — HSTS belongs at the TLS-terminating reverse proxy (see `DEPLOYMENT.md`'s nginx config, which should add it); CSP is not currently configured anywhere and is a real gap for the dashboard's static assets. |

---

## Compliance roadmap (honest, not aspirational)

| Milestone | Status | Blocker |
|---|---|---|
| This CAIQ self-assessment | ✅ Done | — |
| Public Trust Center page | ✅ Done | — |
| NIST CSF self-assessment | ✅ Done | — |
| OWASP ZAP automated scan | Script ready, not yet run against a live deployment | Needs a running instance to scan |
| Dependency vulnerability scanning in CI | ✅ Done — `pip-audit` on every CI run, one finding triaged | — |
| Dependabot (automatic dependency update PRs) | Not started | Engineering time — quick win, should follow soon |
| Formal incident response runbook | Not started | Engineering/process time |
| Third-party penetration test | Not started | **Funding** — typically $5-15K even scoped narrow |
| SOC2 Type II | Not started | **Funding** — $10-30K+/yr tooling plus auditor fees, 6-12mo timeline |
| Sub-processor list (hosted tier) | N/A | No hosted tier exists yet |

This document will be updated as items move off this list — not left stale as marketing collateral.
