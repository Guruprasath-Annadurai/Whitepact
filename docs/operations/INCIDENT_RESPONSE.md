# Incident Response Runbook

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH
CLOSURE MASTER DIRECTIVE, Phase 15. Extends `SECURITY.md` (vulnerability
*disclosure*, inbound reports from third parties) with the operational
lifecycle for handling an incident once one is detected or reported —
severity classification, detection signals, containment actions this
codebase actually has, rollback, and postmortem.

Every containment action named below is grounded in a real, existing
mechanism (file/endpoint cited) — this runbook does not describe
tooling that doesn't exist yet. Where no mechanism exists for an
otherwise-obvious containment step, that's stated explicitly under
"Known gaps," not silently implied.

---

## Severity classification

| Severity | Definition | Examples | Response target |
|---|---|---|---|
| **SEV-1 (Critical)** | Active exploitation, data exposure across tenants, or authentication/authorization bypass in production. | Cross-org data leak; a request executing without a valid `ExecutionAuthorization`; Heart legitimacy bypass; leaked crypto root key. | Acknowledge within 30 min, contain within 4 hours. |
| **SEV-2 (High)** | Real vulnerability confirmed, not yet known to be exploited, or a single-tenant containment failure. | A cross-tenant isolation gap found in the Phase 7 sweep; an expired/tampered `ExecutionAuthorization` accepted. | Acknowledge within 2 hours, contain within 24 hours. |
| **SEV-3 (Medium)** | Degraded security posture without active risk — a control failing open in a way that's detected and logged, not silently. | `verify_heart_production_enforcement()` startup check firing (fail-closed, but signals misconfiguration); audit-chain verification returning `chain_intact: false` for one org. | Acknowledge within 8 hours, contain within 3 business days. |
| **SEV-4 (Low)** | Process/documentation gap, no immediate exploitability. | A dependency finding with no live exploit path (see `docs/security/DEPENDENCY_RISK_REGISTER.md`). | Track, no fixed SLA. |

## Detection signals (what actually surfaces an incident)

Grounded in what this codebase exports today — see
`docs/enterprise-readiness/PHASE5_PURPOSE_BINDING.md`'s and this
phase's own metrics work for the exact names:

- **`whitepact_heart_denials_total`** (Prometheus) — a spike indicates
  either an attack (many illegitimate authority attempts) or a
  misconfiguration (a legitimate integration suddenly failing Heart
  checks). Alert on rate-of-change, not absolute count — legitimate
  denials happen continuously in normal operation.
- **`whitepact_audit_chain_failures_total`** — any non-zero value is a
  SEV-1 by definition: it means `EvidenceRepository.verify_chain()`
  found the hash chain does not reconstruct, i.e. tampering or data
  corruption in the audit trail itself.
- **`whitepact_approval_queue_backlog`** — an unbounded climb can
  indicate either a stuck approval workflow (operational) or an
  attacker flooding `REQUIRE_APPROVAL` actions to exhaust reviewer
  capacity (security).
- **`whitepact_revocations_total`** — a burst of revocations can be
  legitimate (an org offboarding a compromised key en masse) or itself
  the symptom of a compromise being cleaned up — correlate with who
  triggered them (`revoked_by` on the underlying row) before assuming
  either.
- **`GET /api/governance/evidence/verify`** and
  `/api/incident-db/verify` — on-demand tamper-evidence checks, callable
  directly during triage, not only passively scraped.
  `governance_verify_evidence()`/`governance_export_evidence_bundle()`
  in `dashboard/app.py`.
- **Dependabot / CodeQL / Gitleaks / Scorecard** (`.github/workflows/`)
  — supply-chain and secret-leak signals, already running on every PR.
- **Structured logs** (structlog, JSON, request-ID-tagged) — every
  denial, revocation, and Heart-legitimacy failure already logs a
  structured event (e.g. `governance_approval_resolved`,
  `governance_authority_passport_revoked`) queryable by whatever log
  aggregator ingests them; this runbook does not assume a specific one.

## Response lifecycle

### 1. Triage
- Classify severity using the table above.
- Identify affected org(s) — every governed action, evidence record,
  and approval is `org_id`-scoped; a single-tenant incident should stay
  provably single-tenant (see `tests/test_cross_tenant_isolation_sweep.py`,
  Phase 7).
- Pull the relevant `EvidenceRecord` chain (`GET /api/governance/evidence`)
  and, if Heart-related, the `AuthorityGrant`/`ExecutionAuthorization`
  trail for the specific `action_id`.

### 2. Containment — actual mechanisms available today

| Action | Mechanism | Scope |
|---|---|---|
| Revoke a single compromised API key | `DELETE /api/orgs/{org_id}/keys/{key_id}` (`OrgRepository.revoke_key()`) | One key |
| Revoke a consent proof (cuts off consent-backed authority immediately) | `POST /api/governance/consent/{consent_id}/revoke` (`ConsentProofRepository.revoke()`) — live-checked on every subsequent `resolve_authority_grant()` call, no cache | One consent grant |
| Revoke a root authority record | `RootAuthorityRepository.revoke()` — currently has **no REST endpoint**, only reachable via direct DB/admin tooling (see "Known gaps" below) | One root, and everything chained beneath it |
| Force a delegation-graph epoch bump (invalidate all delegated authority downstream) | `RevocationEpochRepository` (Gap B, `docs/heart-production-closure/`) | Whole delegation subtree |
| Deny all future actions for an identity immediately, without deleting history | Revoke the identity's API key(s) AND any consent/root backing it — there is deliberately no soft "suspend" state distinct from revocation (fail-closed: revoked stays revoked, no reversible pause) | One identity |

### 3. Known gaps (state honestly, don't imply a control that doesn't exist)

- **No org-wide kill switch.** There is no single action that
  immediately halts all activity for an org short of revoking every
  key individually (`revoke_key()` is per-key). For a SEV-1 involving
  an entire compromised org, containment today means enumerating and
  revoking every key via `GET /api/orgs/{org_id}/keys` +
  a `DELETE` loop, not one call.
- **No REST endpoint for root-authority revocation.** It exists at the
  repository layer (`RootAuthorityRepository.revoke()`, used internally
  and covered by tests) but is not exposed to an operator without
  direct DB/admin script access. A future phase should add one for
  faster SEV-1 containment.
- **No automated incident ticketing/paging integration.** Detection
  signals above are real; routing them to PagerDuty/Opsgenie/Slack is
  the deploying organization's own responsibility today (webhook
  infrastructure, `webhooks/manager.py`, can be pointed at one).

### 4. Eradication
- Identify root cause using the audit trail (`EvidenceRecord` chain,
  `AuthorityGrant`/`ExecutionAuthorization` fields — as of Phase 3
  these carry `consent_reference`/`policy_version`/
  `heart_legitimacy_digest`/`execution_id`, enough to reconstruct
  exactly what was checked and against what).
- If the root cause is a code defect, follow this repository's standing
  discipline: write a regression test proving the specific failure
  mode first, then fix, then verify the fix against the full suite —
  the same pattern used for the singleton bug found and fixed during
  Phase 4, and the `_agent_from_approval()` agent-id bug found and
  fixed during Phase 5.

### 5. Recovery
- Re-issue credentials for legitimately affected identities.
- If revocation over-corrected (a legitimate identity was caught in a
  broad revocation), a **new** root/consent/key must be issued —
  revocation is deliberately one-way (matches `resolve_root_for_identity()`'s
  own documented "does not silently re-issue a fresh root for a
  revoked identity" behavior); there is no "un-revoke."
- Run `GET /api/governance/evidence/verify` (or the org-scoped
  equivalent) to confirm the audit trail is intact post-incident.

### 6. Postmortem
- Every incident gets a written postmortem: timeline, root cause,
  what detected it (or the gap if nothing did), what contained it,
  what changed as a result (code, config, or this runbook itself).
- Update `docs/security/DEPENDENCY_RISK_REGISTER.md` if the incident
  involved a dependency.
- Update this runbook's "Known gaps" section if the incident exposed a
  containment mechanism that should exist but doesn't yet — do not
  silently patch the gap in code without also removing the stale
  "Known gaps" entry, and vice versa.

## Disaster-recovery cross-reference

A SEV-1 involving data loss or corruption (not just unauthorized
access) follows `SLA.md`'s stated RPO/RTO and
`docs/operations/DR_RESTORE_DRILL.md`'s (Phase 16) restore procedure,
not this document's containment steps alone.

## Ownership and escalation

Reports and incidents route through `SECURITY.md`'s contact
(**annaduraiguruprasath7@gmail.com**) until a dedicated on-call rotation
exists — this document does not fabricate a rotation or paging schedule
that isn't actually staffed yet.
