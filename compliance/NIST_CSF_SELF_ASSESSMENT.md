# NIST Cybersecurity Framework (CSF 2.0) Self-Assessment — ResponsibleAI Platform v1.2.0

This maps the platform's actual security posture against NIST CSF 2.0's six
functions. It is a self-assessment, not a third-party audit — no auditor
has reviewed these maturity ratings. Do not conflate this with **NIST AI
RMF**, which the platform implements as a *product feature*
(`rai_compliance`, `GET /api/compliance/check`) for evaluating customers'
AI systems — this document is about the platform's own infosec posture,
a different and unrelated framework despite the similar name.

**Maturity scale used below:** Not Implemented → Partial → Defined → Managed → Optimized.
Where an item is below "Managed," that's stated plainly rather than rounded up.

Last reviewed: 2026-07-21 · Platform version: 1.2.0

---

## GOVERN (GV) — Establish and monitor cybersecurity risk management strategy

| Subcategory | Maturity | Evidence |
|---|---|---|
| GV.OC — Organizational context understood | Defined | Solo-maintained open-source project; threat model and scope documented in `SECURITY.md`, `ENTERPRISE_SECURITY.md`. |
| GV.RM — Risk management strategy established | Partial | No formal, scheduled risk-review cadence. Risks are addressed reactively (audit → fix → document) rather than via a standing risk register. Real gap for a team of one; would need to change before scaling headcount. |
| GV.RR — Roles and responsibilities defined | Partial | Single maintainer holds all roles today (`SECURITY.md` contact). RBAC (`OWNER/ADMIN/ANALYST/VIEWER`) defines *customer-facing* roles precisely; internal maintainer role separation doesn't apply yet at current team size. |
| GV.PO — Policy established and communicated | Defined | `SECURITY.md` (vulnerability disclosure), `ENTERPRISE_SECURITY.md` (controls posture), `SLA.md` (commitments), this document and the CAIQ self-assessment. |
| GV.OV — Oversight of risk management | Not Implemented | No board/exec oversight function exists at current company stage (pre-funding, solo founder). Will need building before any formal certification (SOC2 requires demonstrable management oversight). |
| GV.SC — Supply chain risk managed | Partial | Dependencies declared with version constraints; `pip-audit` now scans every CI run (see CAIQ Domain 15). Vendor risk assessment for third-party services now exists (`compliance/VENDOR_RISK_ASSESSMENT.md`, covering OCI, Stripe, customer-owned OIDC/LLM vendors) — still a one-time, opportunistic write-up rather than a scheduled recurring process, which the document itself states plainly. |

---

## IDENTIFY (ID) — Understand assets, risks, and vulnerabilities

| Subcategory | Maturity | Evidence |
|---|---|---|
| ID.AM — Asset management | Defined | Codebase is the entire asset surface (open source, fully inspectable); data assets enumerated in `ENTERPRISE_SECURITY.md` (trust scores, cost/token usage, audit log, org/API key data). |
| ID.RA — Risk assessment | Partial | No formal, periodic risk assessment. `ENTERPRISE_SECURITY.md` documents known gaps as they're found (encryption-at-rest scope, SAML absence, audit chain limitations) rather than via a structured methodology. |
| ID.IM — Improvement identified | Managed | Gaps are tracked and closed with evidence, not just noted — e.g., the auto-migration bug found and fixed this cycle, tiered rate limiting, dependency scanning. This document's own roadmap table is the improvement log. |

---

## PROTECT (PR) — Safeguards to manage cybersecurity risk

| Subcategory | Maturity | Evidence |
|---|---|---|
| PR.AA — Identity management, authentication, access control | Managed | RBAC with 4 strictly hierarchical roles enforced on every endpoint; OIDC SSO with enforceable SSO-only mode (`PUT /api/orgs/{id}/sso`) closing the static-key-backdoor gap; API keys stored as SHA-256 hashes only, revocable immediately. |
| PR.AT — Awareness and training | Not Implemented | No formal security training program — not applicable at current team size (solo maintainer). Flagged for when a team exists, not glossed over. |
| PR.DS — Data security | Partial | PII detection/redaction (Guardrails Engine) is strong. Encryption at rest is explicitly the deployer's responsibility (documented, not hidden). Opt-in field-level encryption now covers `audit_log.ip_address` (`RAI_FIELD_ENCRYPTION_KEY`) — the one standalone PII column — but not every column with free-text metadata. Multi-tenant isolation via `org_id` filtering on every governance data table. |
| PR.PS — Platform security | Managed | Non-root containers, dropped capabilities, `readOnlyRootFilesystem` where applicable, explicit zero-downtime rollout strategy, PodDisruptionBudget, internal-only network isolation for Postgres/Redis in the reference compose stack. |
| PR.IR — Technology infrastructure resilience | Defined | Redis+Postgres production stack, documented DR (RPO 24h/RTO 1-4h), backup/restore scripts. `DatabaseEngine.init()` retries transient connection failures with backoff (up to 5 attempts, exponential) — real protection against the app crashing hard during a brief DB failover window at startup. **Still not automated replica failover**: promoting a replica to primary itself (Patroni, RDS/Cloud SQL Multi-AZ, streaming replication) remains the deployer's Kubernetes/cloud responsibility — no application code substitutes for that. |

---

## DETECT (DE) — Find and analyze cybersecurity events

| Subcategory | Maturity | Evidence |
|---|---|---|
| DE.CM — Continuous monitoring | Defined | Prometheus metrics (`/metrics`), Grafana dashboard built against the metrics that actually exist (an earlier version queried metrics that didn't exist at all — caught and rebuilt), alert rules for error rate, trust score degradation, guardrail block spikes, drift, cost spikes, webhook failures. |
| DE.AE — Adverse event analysis | Partial | Hash-chained audit trail (`GET /api/audit/verify`) detects tampering. No automated anomaly-detection/correlation layer beyond the Prometheus alert rules. A human no longer has to manually log what an alert caught, though — a firing alert now auto-creates a queryable `incidents` row via `POST /api/alerts/webhook` (see `grafana/prometheus/alertmanager.yml.example`); a human still has to look at the dashboard/incident and actually respond. |
| DE.OC — Anomalies and events reported | Managed | `rai_incident_log` MCP tool produces structured, SIEM-ready incident records with severity classification and evidence hashing. |

**Resolved, stated plainly:** the governance metrics (trust score, cost, tokens, guardrail scans, drift alerts, webhook deliveries) now carry an `org_id` label, so per-tenant observability is possible — Prometheus/Grafana queries can filter or break down by org. Default alert rules and dashboard panels still show platform-wide totals by design (see `grafana/prometheus/alert-rules.yml`), since alerting on every individual tenant isn't yet needed at current scale. The tradeoff, disclosed rather than hidden: per-tenant labels multiply Prometheus series cardinality by org count — fine for today's scale, worth revisiting (e.g. dropping the label at the scrape-config relabeling stage) if a deployment grows to thousands of active orgs.

---

## RESPOND (RS) — Take action on detected cybersecurity incidents

| Subcategory | Maturity | Evidence |
|---|---|---|
| RS.MA — Incident management | Defined | `SECURITY.md` covers vulnerability disclosure response with concrete timelines (48h ack, 7-day resolution target). `compliance/INCIDENT_RESPONSE_RUNBOOK.md` documents the full internal process (detect → triage → contain → eradicate → recover → notify → post-incident review), aligned with `SLA.md`'s P1–P4 severity scale. One tabletop drill completed (`compliance/TABLETOP_EXERCISE_2026-07-21.md`), which found and fixed two real gaps (a missing incident-logging habit, a tool referencing a nonexistent persistence endpoint). **Not yet "Managed"**: one drill is not a real production incident, and NIST CSF's "Managed" level implies an ongoing, periodically-repeated practice — this is a single data point, not yet a consistent one. |
| RS.CO — Incident communication | Not Implemented | No formal breach-notification SLA (e.g., GDPR's 72-hour requirement) is documented as a standing commitment. Must be built before signing any contract that requires one — flagged as a pre-contract blocker, not assumed handled. |
| RS.AN — Incident analysis | Managed | `rai_incident_log`'s evidence hashing and SIEM payload structure support post-incident analysis once an incident is logged. |

---

## RECOVER (RC) — Restore assets and operations after an incident

| Subcategory | Maturity | Evidence |
|---|---|---|
| RC.RP — Recovery plan executed | Defined | `scripts/backup-postgres.sh` / `restore-postgres.sh`, documented RPO/RTO per tier in `SLA.md`, `DEPLOY_RUNBOOK.md`'s rollback procedure for failed deploys. |
| RC.CO — Recovery communication | Not Implemented | No documented customer-communication plan during an active recovery event (status page copy, escalation contacts beyond the general security email). Real gap for a paying-customer scenario, not yet built. |

---

## Overall maturity summary

| Function | Dominant maturity level |
|---|---|
| Govern | Partial — expected at current company stage (pre-funding, solo founder); would need real investment before pursuing formal certification |
| Identify | Partial to Defined |
| Protect | Defined to Managed — the strongest function, reflecting where actual engineering effort has concentrated (RBAC, SSO enforcement, multi-tenancy, container hardening) |
| Detect | Defined |
| Respond | Defined — the internal runbook exists and has been through one tabletop drill (2026-07-21, two real gaps found and fixed); still untested against a real production incident. The committed breach-notification SLA remains a Govern-adjacent legal gap, not a Respond gap |
| Recover | Defined |

**Honest bottom line:** the platform's *technical* controls (Protect, Detect) are ahead of its *organizational* controls (Govern) — typical for a solo-maintained project where engineering time is cheap relative to process/legal time. Respond moved from Partial to Defined once the internal runbook was written — that was pure documentation/process work, genuinely buildable without a certification budget. What's left in Respond/Govern now needs either a real incident to test the runbook against, or an attorney for the breach-notification commitment (see `compliance/DPA_ATTORNEY_SCOPE_BRIEF.md`) — the next investment should go toward Govern's oversight/risk-review gaps, since Respond's documentation work is done.
