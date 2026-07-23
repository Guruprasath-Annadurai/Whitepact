# SOC 2 Readiness Assessment — ResponsibleAI Platform v1.2.0

> ## ⚠️ This is a readiness accelerant, not a SOC 2 report
>
> This document is **not** a SOC 2 Type I or Type II report, is **not**
> produced by a licensed CPA firm, and confers **no certification**. A real
> SOC 2 requires an independent AICPA-accredited auditor examining actual
> operating evidence — access logs, change tickets, onboarding/offboarding
> records — over an observation window (Type I: a point in time; Type II:
> typically 3–12 months). No amount of internal documentation substitutes
> for that independence or that evidence trail.
>
> What this *is*: a control-by-control map of the AICPA Trust Services
> Criteria (TSC) against what this codebase and this solo-maintained project
> actually do today, an honest list of what's missing, and a scoped estimate
> of what it would take to engage a real auditor. The goal is that if/when a
> CPA firm is engaged, the audit is faster and cheaper because the gaps are
> already known rather than discovered mid-engagement.
>
> This should be read alongside `compliance/CAIQ_SELF_ASSESSMENT.md` (control
> inventory, cloud-security-questionnaire format) and
> `compliance/NIST_CSF_SELF_ASSESSMENT.md` (maturity ratings by NIST
> function) — this document doesn't duplicate their content, it maps the same
> underlying facts onto the specific TSC categories a SOC 2 auditor scopes
> against.

Last reviewed: 2026-07-23 · Platform version: 1.2.0

---

## 1. Scoping — what a SOC 2 examination would actually cover here

- **Entity under examination**: Guruprasath Annadurai, operating as the
  ResponsibleAI project (sole proprietor — no separate legal entity formed).
  A real auditor will need to know this before scoping; sole-proprietor
  engagements are unusual but not unheard of for early-stage vendors.
- **System boundary**: as of this version, **there is no
  Provider-operated production system to examine** — see `SLA.md`'s Scope
  section: *"as of v1.2.0, no ResponsibleAI-operated hosted instance is live
  yet."* SOC 2 examines the controls of an *operating* system over a
  window of time. Until a hosted instance exists and has been running long
  enough to generate evidence, there is nothing to audit against — this is
  the same dependency called out as the top gap in the broader enterprise
  gap list this document responds to.
- **What can be scoped today**: the self-hosted software's *security design*
  (code, container hardening, CI gates) can be reviewed now, and is — see
  Section 3. What cannot be scoped today: *operational* evidence (who
  accessed what, when access was revoked, incident response actually
  exercised against a live system) because there is no live system
  generating that evidence yet.
- **Recommended sequencing**: (1) stand up and operate a hosted instance for
  at least one full quarter, generating real access logs, change records, and
  at least one exercised incident-response cycle; (2) engage a CPA firm for a
  **Type I** report first (design of controls at a point in time — cheaper,
  faster, and the natural first step); (3) operate under those controls for
  3–12 months to accumulate Type II evidence; (4) engage for **Type II**
  (operating effectiveness over the window). Do not attempt to skip to Type
  II — most auditors won't, and it wastes money re-scoping mid-engagement.

---

## 2. Trust Services Criteria mapping

Each TSC category below cites the specific control and its exact
implementation, not a restated claim. **Security** is required in every SOC 2
scope; the other four are selected based on what the engagement needs to
cover — a recommendation on which to include is given per category.

### 2.1 Security (Common Criteria — required in every SOC 2 scope)

| Control area | Implemented | Evidence |
|---|---|---|
| Logical access controls | Yes | RBAC (Owner/Admin/Analyst/Viewer), strictly hierarchical, enforced on every endpoint. API keys stored as SHA-256 hashes only, revocable immediately (`DELETE /api/orgs/{id}/keys/{key_id}`), checked live on every `authenticate()` call — not cached. |
| Authentication strength | Yes | OIDC/SSO for org identity, with enforceable SSO-only mode (`PUT /api/orgs/{id}/sso`). TOTP MFA (RFC 6238) at the one interactive human login step (`POST /api/auth/login-key`), org-enforceable (`PUT /api/orgs/{id}/mfa`), single-use backup codes (`auth/mfa.py`). |
| Encryption in transit | Deployer-dependent | App speaks plain HTTP internally; TLS termination is the reverse proxy's job (`DEPLOYMENT.md`'s nginx config). **Gap for a from-scratch SOC 2**: an auditor will want this enforced/documented as a standing requirement, not an option, for any hosted instance. |
| Encryption at rest | Partial | Whole-database encryption is the deployer's infrastructure choice (documented, not hidden — see `ENTERPRISE_SECURITY.md`). Opt-in application-layer field encryption (`RAI_FIELD_ENCRYPTION_KEY`, `db/encryption.py`) covers four PII/secret columns: `audit_log.ip_address`, `public_incident_reports.reporter_name`/`.reporter_contact`, `webhook_configs.secret`, `org_api_keys.mfa_secret`. **Gap**: not every free-text column (e.g. incident `description`) is covered; key management for `RAI_FIELD_ENCRYPTION_KEY` itself (rotation, storage) is not yet formalized. |
| Vulnerability management | Partial | `pip-audit` runs on every CI run (zero known vulnerabilities in the mandatory dependency set as of this version — see Domain 15 in the CAIQ assessment for the nltk PYSEC-2026-597 resolution). Automated OWASP ZAP baseline scan exists (`scripts/security-scan.sh`), explicitly documented throughout the repo as **not** a substitute for a third-party penetration test. Internal manual security review documented in `compliance/INTERNAL_SECURITY_REVIEW.md`. **Gap**: no third-party penetration test has been performed (cost-gated, $5-15K; see Section 4). |
| Change management | Yes | Alembic migrations, version-controlled, auto-applied at startup (fatal-on-failure, not silently degraded). CI gates every merge on the full test suite (1000+ tests), mypy strict-optional, ruff, and `helm lint`. |
| Incident response | Partial | `compliance/INCIDENT_RESPONSE_RUNBOOK.md` documents the full internal process, aligned with `SLA.md`'s P1–P4 severity scale. One tabletop drill completed and documented (`compliance/TABLETOP_EXERCISE_2026-07-21.md`), which found and fixed two real process gaps. An internal 72-hour breach-notification target now exists (adopted 2026-07-23, Phase 5 of the runbook) — an operational standard, not yet a contractual DPA term. **Gap**: a SOC 2 auditor will want this exercised against a real production incident, not only a tabletop drill — not yet possible without a live hosted instance (Section 1). |
| Governance / risk oversight | Partial | A formal quarterly risk-review cadence now exists (`GOVERNANCE.md`, adopted 2026-07-23) — real process, not just a policy statement. What it explicitly does not fix, stated in that same document: no board or executive oversight function exists, so the cadence is disciplined self-assessment, not independent oversight. This is precisely the control SOC 2's Common Criteria (CC1: Control Environment) examines first. An auditor will ask "who oversees the person who built this," and today the honest answer is still "no one does yet." This needs a real answer (an advisor, a fractional CISO, a named second person with actual authority) before a credible engagement — a founder decision, not something further documentation can substitute for. |
| Personnel security | Not Implemented | No formal background-check or security-training program — not applicable at current team size (solo maintainer). Will need building before scaling headcount, and before a SOC 2 auditor will accept "no policy needed" as a permanent answer rather than a stage-appropriate one. |

### 2.2 Availability

Recommended: **include**, once a hosted instance exists — this is the
category most directly relevant to the "no hosted instance" gap.

| Control area | Implemented | Evidence |
|---|---|---|
| Uptime commitments | Documented | `SLA.md`'s tiered uptime table (FREE 99.0% design target/not enforced, PRO 99.5%, ENTERPRISE 99.9%) — **not yet backed by an operating hosted instance to measure against**. |
| Redundancy / failover | Partial | Multi-replica horizontal scaling supported (Helm chart, HPA); `DatabaseEngine.init()` retries transient connection failures with capped exponential backoff. **Gap, stated plainly**: automated failover *orchestration* (promoting a DB replica to primary) is not built into the app — it remains the deployer's Kubernetes/cloud-provider responsibility. |
| Disaster recovery | Yes | Documented RPO 24h (nightly `pg_dump`) / RTO 1-4h by tier, `scripts/backup-postgres.sh` / `restore-postgres.sh`, DR plan in `SLA.md`. |
| Capacity monitoring | Yes | Prometheus metrics (`/metrics`), Grafana dashboards built against metrics that actually exist, alert rules for error rate, cost spikes, webhook failures. |

### 2.3 Confidentiality

Recommended: **include** — directly relevant to an enterprise buyer's data
handling concerns.

| Control area | Implemented | Evidence |
|---|---|---|
| Data classification | Partial | Public-by-design features (Trust Leaderboard, Trust Index verification pages, AI Incident Database) are explicitly separated from confidential account/content data in `PRIVACY_POLICY.md` Section 3. No formal internal data-classification policy document exists beyond that. |
| Confidentiality commitments | Documented, not yet attorney-reviewed | `TERMS_OF_SERVICE.md` Section 8 (confidentiality clause, placeholder pending counsel), `compliance/DPA_TEMPLATE.md` (data processing terms, same status). |
| Multi-tenant isolation | Yes | `org_id` filtering enforced on every governance data table, including `webhook_configs` as of this version. |

### 2.4 Processing Integrity

Recommended: **evaluate case-by-case** — relevant mainly if a buyer's
procurement process specifically asks for it; most SaaS vendors at this
stage scope Security + Availability + Confidentiality only.

| Control area | Implemented | Evidence |
|---|---|---|
| Input validation | Yes | Every REST endpoint uses Pydantic request models with explicit field constraints. |
| Audit trail integrity | Yes | Hash-chained `audit_log` table (`entry_hash = sha256(prev_hash + fields)`); `GET /api/audit/verify` recomputes the chain and reports the first broken link. Detects direct DB tampering — not a fully compromised database with write access, a limitation documented in `ENTERPRISE_SECURITY.md`. |
| Output accuracy disclaimers | Yes | `TERMS_OF_SERVICE.md` Section 9 states plainly that trust scores, compliance classifications, and hallucination detection are automated heuristics, not guarantees. |

### 2.5 Privacy

Recommended: **include** if the hosted instance will process personal data
directly (likely, given account/API-key data) — otherwise this overlaps
heavily with GDPR/CCPA obligations already covered by `PRIVACY_POLICY.md`.

| Control area | Implemented | Evidence |
|---|---|---|
| Notice and disclosure | Documented, not yet attorney-reviewed | `PRIVACY_POLICY.md` — itself explicitly a draft pending counsel review and pending re-verification against a live system (see that document's own header). |
| Data subject rights | Documented | `PRIVACY_POLICY.md` Section 7, contact `milchcreamfoods@gmail.com`. Response-timeframe commitment is an explicit placeholder pending counsel. |
| PII handling / minimization | Yes | Guardrails Engine PII detection/redaction; opt-in field-level encryption for the PII columns enumerated in Section 2.1 above. |

---

## 3. What's already strong (don't re-build this for an auditor)

- RBAC + OIDC SSO + TOTP MFA covering the full authentication surface.
- Hash-chained, independently-verifiable audit trail.
- CI-gated dependency scanning (`pip-audit`) with a real, resolved
  vulnerability (nltk PYSEC-2026-597) as evidence the process works, not
  just exists on paper.
- Documented, exercised (if only once) incident-response runbook — most
  early-stage vendors have the runbook but have never actually drilled it.
- Existing self-assessments (`CAIQ_SELF_ASSESSMENT.md`,
  `NIST_CSF_SELF_ASSESSMENT.md`, `compliance/VENDOR_RISK_ASSESSMENT.md`) give
  an auditor a running start instead of a blank slate — most of the
  evidence-gathering interview a CPA firm would normally spend billable
  hours on is already answered in writing.

---

## 4. Honest gap list — what has to happen before a real engagement

1. **No hosted instance to audit** (Section 1) — the load-bearing blocker.
   Nothing else on this list matters until this exists and has run long
   enough to generate operating evidence.
2. **No independent governance/oversight function** (Section 2.1) — a
   named second person with real authority (advisor, fractional CISO, or
   eventual co-founder) is what CC1 actually expects, and no process
   document can substitute for that; this is the one item on this whole
   list that is purely a founder decision, not an engineering or
   documentation task.
3. **No formal risk register** — a scheduled quarterly review cadence now
   exists (`GOVERNANCE.md`, adopted 2026-07-23), closing part of the GV.RM
   gap `NIST_CSF_SELF_ASSESSMENT.md` previously flagged, but a running,
   structured, scored risk register is still a separate, not-yet-built
   artifact from the cadence that will review it.
4. **No *contractual* breach-notification SLA** — an internal 72-hour
   operational target now exists (adopted 2026-07-23,
   `compliance/INCIDENT_RESPONSE_RUNBOOK.md` Phase 5), but turning that
   into a binding DPA term still requires the process to be proven against
   a real incident (not just one tabletop drill) and the language set by
   counsel — tracked in `compliance/DPA_ATTORNEY_SCOPE_BRIEF.md` §7.
5. **No third-party penetration test** — cost-gated at $5-15K, tracked
   separately (see `compliance/INTERNAL_SECURITY_REVIEW.md` for what's been
   done in its place in the meantime).
6. **Key management for `RAI_FIELD_ENCRYPTION_KEY`** — now formalized as of
   2026-07-23: `compliance/KEY_MANAGEMENT.md` documents custody guidance and
   a real rotation procedure, backed by actual mechanism (`MultiFernet`
   multi-key support in `db/encryption.py` plus
   `scripts/rotate_field_encryption_key.py` to re-encrypt existing rows).
   What's still genuinely open: this has never been *exercised* against a
   real production database with real data at stake — the procedure is
   documented and the mechanism is tested, but "written down" and "actually
   followed under real conditions" are different bars, and only the first
   is met yet.
7. **Entity structure** — a sole proprietor engagement is unusual for SOC 2;
   confirm with the CPA firm at initial scoping conversation whether this
   changes the engagement letter or requires entity formation first.

---

## 5. Estimated cost and timeline (informational only — get real quotes)

These are rough, publicly-known market ranges for a small-scope SaaS vendor,
not a quote from any specific firm — get actual proposals before budgeting:

| Item | Typical range | Notes |
|---|---|---|
| Readiness/gap consulting (optional) | $5K–$15K | Often skippable if this document and the existing self-assessments are used directly with the audit firm. |
| SOC 2 Type I | $10K–$30K | Point-in-time design review; realistic first engagement once a hosted instance exists. |
| SOC 2 Type II | $20K–$60K+ | Requires 3–12 months of *operating* evidence after Type I; cost scales with scope (number of TSC categories) and observation window length. |
| Ongoing annual re-certification | Similar to initial Type II | SOC 2 is not a one-time credential — it's re-examined annually. |

---

## Before treating this document as "SOC 2 done"

1. This is not a certification. Do not represent it as one to a customer,
   in a sales deck, or on the Trust Center page — doing so would be the
   exact fabrication this document exists to avoid.
2. Nothing here substitutes for engaging a real, AICPA-accredited CPA firm.
   Use this document as the intake packet for that conversation, not as a
   replacement for it.
3. Re-verify Section 1's "no hosted instance" gap before doing anything
   else on this list — it blocks nearly every other item and its status may
   have changed since this was last reviewed.
4. Update the "Last reviewed" date whenever a control's actual
   implementation changes, the same discipline already applied to
   `compliance/CAIQ_SELF_ASSESSMENT.md` and
   `compliance/NIST_CSF_SELF_ASSESSMENT.md`.
