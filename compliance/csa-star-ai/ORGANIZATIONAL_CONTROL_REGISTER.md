# Organizational control register

Honest posture: **solo-maintained** organization. No HR department, no independent internal audit function.

| Control theme | Required practice | Accountable owner | Status | Evidence | Review cadence | Last reviewed | Next review |
|---------------|-------------------|-------------------|--------|----------|----------------|---------------|-------------|
| Security awareness | Founder maintains secure engineering practices; no formal LMS | Founder / Security Owner | Documented | This register + `GOVERNANCE.md` | Annual | 2026-09-23 | 2027-09-23 |
| Personnel onboarding | N/A — no employees | Founder | **NA (defensible)** | Solo maintainer statement | When hiring | 2026-09-23 | On first hire |
| Personnel offboarding | Policy draft: revoke access within 24h when contractors added | Founder | Policy when needed | Future HR policy appendix | On first hire | — | — |
| Access review | Quarterly review of GitHub, hosting, Paddle, DNS admin accounts | Founder | **OWNER ACTION** OA-003 | Account list + MFA screenshots | Quarterly | — | 2026-12-23 |
| Incident roles | Founder = incident commander | Founder | Operating (solo) | `INCIDENT_RESPONSE_RUNBOOK.md`, exercise 2026-09-23 | Annual exercise | 2026-09-23 | 2027-09-23 |
| Vendor review | Quarterly subprocessor register update | Founder | In progress | `SUBPROCESSOR_REGISTER.md` | Quarterly | 2026-09-23 | 2026-12-23 |
| Risk review | Threat model + CAIQ evidence boundary review | Founder | Operating | `THREAT_MODEL.md`, `CAIQ_EVIDENCE_BOUNDARY.md` | Semi-annual | 2026-08-31 | 2027-02-28 |
| Policy review | Update policies when codebase changes | Founder | Operating | Git history + compliance docs | Continuous | 2026-09-23 | — |
| Endpoint security (EDM) | FileVault, screen lock, OS updates, no shared admin laptop | Founder | **OWNER ASSERTION** OA-006 | Self-attestation | Annual | Pending | 2026-10-23 |
| Physical datacenter | None — CSP responsibility | Cloud provider | **Provider SSRM** | OA-002 | Annual | — | — |

Do not mark rows YES in AI-CAIQ until evidence column is populated.
