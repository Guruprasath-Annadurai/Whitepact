# WhitePact SOC 2 Readiness Addendum — 2026-09-13

**Status:** First-party readiness addendum; not a SOC 2 report  
**Applies with:** `compliance/SOC2_READINESS.md`  
**Baseline:** `main@8f8ef53f0460c99115f5656dfa4d31775bca4d6a` plus the pre-audit assurance closure branch

## Why this addendum exists

The original SOC 2 readiness assessment contains historical statements from the period before WhitePact had an operating hosted reference service. Those statements are useful history but no longer describe the current privacy-policy scope, which documents Provider-operated hosted endpoints and current subprocessors.

This addendum supersedes only stale current-state assumptions; it does not erase historical evidence or convert first-party controls into an independent SOC 2 examination.

## 1. Current system boundary

A reasonable future SOC 2 scope should include, subject to auditor scoping:

- Provider-operated WhitePact hosted/reference service;
- production application/API/MCP surfaces in scope for customers;
- identity/access administration;
- governance decision and evidence paths;
- source/release pipeline supporting the service;
- production data stores/cache/infrastructure subprocessors;
- monitoring, incident response, backup/recovery and key/secret operations;
- relevant vendor/subprocessor controls.

Self-hosted customer environments remain customer-operated; WhitePact's software design, release integrity and support process may be relevant, but customer cloud/runtime operations are not automatically WhitePact controls.

## 2. Trust Services Criteria readiness posture

| Area | Current first-party posture | Remaining evidence need |
|---|---|---|
| Security | Strong design/process baseline | independent audit, exact-release evidence, production access/operation history |
| Availability | Partial/meaningful controls | measured uptime, restore/failover exercises, clearer resilience evidence |
| Confidentiality | Strong policy/access/tenant baseline | contract execution/counsel review, operating access-review evidence |
| Processing Integrity | Strong governance/audit design | exact-release operational evidence and customer-use scoping |
| Privacy | Documented/partial | retention enforcement evidence, real rights-request evidence as events occur, counsel validation |

## 3. Internally completable SOC 2 work — status

| Readiness task | Status after this branch |
|---|---|
| Control inventory | Complete first-party baseline via `ENTERPRISE_ASSURANCE_MASTER_INDEX.md` |
| Formal risk method/register | Complete first-party baseline via `RISK_MANAGEMENT_POLICY.md` |
| Security/AI governance policies | Complete first-party baseline |
| Incident response procedure | Existing and exercised by tabletop |
| Vendor/subprocessor assessment | Existing |
| Continuity/DR plan | Existing; resilience proof remains partial |
| Vulnerability management | Existing first-party program |
| Change/release governance | Existing protected CI/release controls |
| Privacy/DPA/ToS readiness | Existing drafts/policy; counsel review external |
| Auditor evidence index | Complete first-party baseline via master index |
| Exact-release evidence procedure | Defined; execute once V1 release SHA is frozen |

## 4. Operating-evidence register to begin/continue now

SOC 2 Type II depends on control operation over time. WhitePact should retain dated evidence for:

- privileged/admin access reviews;
- API-key/credential lifecycle and revocation;
- production changes and release approvals;
- CI/security scan results;
- vulnerability findings/remediation;
- backup completion and restore exercises;
- incident/tabletop exercises;
- vendor reviews;
- risk reviews;
- security exceptions/risk acceptance;
- customer/privacy requests when they occur;
- production monitoring/availability;
- key rotation exercises;
- exact-release provenance/SBOM/signing.

Do not manufacture empty tickets or fake historical events. Where no real event occurred, evidence should say **no event during period** and show the monitoring/process that would handle one.

## 5. Remaining non-documentation gaps

1. **Independent CPA/audit firm** — external-only.
2. **Observation period** for Type II — elapsed operating time cannot be compressed by documentation.
3. **Independent penetration/security assessment** — external-only if independence is claimed.
4. **Oversight/separation of duties** — current solo-maintainer concentration is a real residual risk.
5. **Resilience evidence** — cross-region/HA posture must match what is actually sold/promised.
6. **Retention enforcement evidence** — adopted privacy schedules need technical/manual operating proof.
7. **Counsel-reviewed contractual language** — not a SOC 2 requirement by itself in every case, but important for enterprise privacy/confidentiality commitments.

## 6. Recommended eventual examination path

- Freeze the enterprise system boundary and exact release.
- Complete independent pentest/remediation where feasible before audit fieldwork.
- Engage a qualified SOC 2 auditor for scoping/readiness confirmation.
- Consider Type I first if buyer pressure requires near-term independent design assurance.
- Accumulate a clean operating window for Type II.
- Avoid adding unnecessary TSC categories until customer requirements justify the additional scope.

## 7. Claim boundary

Allowed now: **"WhitePact has a documented SOC 2 readiness/control-evidence program and is preparing operating evidence for future independent examination."**

Not allowed: **"SOC 2 certified," "SOC 2 compliant," "SOC 2 audited," or "SOC 2 Type I/II"** without the actual independent report and correct scope/date.
