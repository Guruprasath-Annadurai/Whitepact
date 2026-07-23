# NIST Cybersecurity Framework (CSF 2.0) Self-Assessment — {{COMPANY_NAME}}

> This maps {{COMPANY_NAME}}'s actual security posture against NIST CSF
> 2.0's six functions. It is a self-assessment, not a third-party audit —
> no auditor has reviewed these maturity ratings unless you say so
> explicitly below.
>
> **Maturity scale**: Not Implemented → Partial → Defined → Managed →
> Optimized. **Rate honestly** — rounding up a "Partial" to "Defined"
> because it's embarrassing is exactly the kind of gap a real auditor
> catches immediately, and catching one inflated rating makes them
> distrust every other rating in the document.

Last reviewed: {{DATE}} · Prepared for: {{COMPANY_NAME}}

---

## GOVERN (GV) — Establish and monitor cybersecurity risk management strategy

| Subcategory | Maturity | Evidence |
|---|---|---|
| GV.OC — Organizational context understood | [FILL IN] | [FILL IN: where is your threat model/scope documented, if anywhere?] |
| GV.RM — Risk management strategy established | [FILL IN] | [FILL IN: is there a scheduled risk-review cadence, or reactive-only?] |
| GV.RR — Roles and responsibilities defined | [FILL IN] | [FILL IN: who holds which security role today — even "one person holds all of them" is a valid, honest answer at an early stage.] |
| GV.PO — Policy established and communicated | [FILL IN] | [FILL IN: list the actual policy documents that exist.] |
| GV.OV — Oversight of risk management | [FILL IN] | [FILL IN: is there any oversight function beyond the person who built the system? Say "not yet" if true.] |
| GV.SC — Supply chain risk managed | [FILL IN] | [FILL IN: dependency scanning tooling, vendor risk review process, or neither yet?] |

## IDENTIFY (ID) — Understand assets, risks, and vulnerabilities

| Subcategory | Maturity | Evidence |
|---|---|---|
| ID.AM — Asset management | [FILL IN] | [FILL IN: is there an inventory of what data/systems exist?] |
| ID.RA — Risk assessment | [FILL IN] | [FILL IN: formal methodology, or ad-hoc as issues are found?] |
| ID.IM — Improvement identified | [FILL IN] | [FILL IN: is there a tracked log of gaps found and closed?] |

## PROTECT (PR) — Safeguards to manage cybersecurity risk

| Subcategory | Maturity | Evidence |
|---|---|---|
| PR.AA — Identity management, authentication, access control | [FILL IN] | [FILL IN: RBAC, SSO, MFA — what actually exists?] |
| PR.AT — Awareness and training | [FILL IN] | [FILL IN: formal program, or not applicable at current team size?] |
| PR.DS — Data security | [FILL IN] | [FILL IN: encryption at rest/in transit, at what layer?] |
| PR.PS — Platform security | [FILL IN] | [FILL IN: container/infra hardening measures, if any.] |
| PR.IR — Technology infrastructure resilience | [FILL IN] | [FILL IN: redundancy, documented DR, backup/restore tested or not.] |

## DETECT (DE) — Find and analyze cybersecurity events

| Subcategory | Maturity | Evidence |
|---|---|---|
| DE.CM — Continuous monitoring | [FILL IN] | [FILL IN: what's actually monitored — metrics, logs, alerts?] |
| DE.AE — Adverse event analysis | [FILL IN] | [FILL IN: automated anomaly detection, or manual review only?] |
| DE.OC — Anomalies and events reported | [FILL IN] | [FILL IN: is there a structured incident-logging mechanism?] |

## RESPOND (RS) — Take action on detected cybersecurity incidents

| Subcategory | Maturity | Evidence |
|---|---|---|
| RS.MA — Incident management | [FILL IN] | [FILL IN: does a written incident response runbook exist? Has it ever been drilled?] |
| RS.CO — Incident communication | [FILL IN] | [FILL IN: is there any breach-notification commitment, internal or contractual?] |
| RS.AN — Incident analysis | [FILL IN] | [FILL IN: post-incident review process, if any.] |

## RECOVER (RC) — Restore assets and operations after an incident

| Subcategory | Maturity | Evidence |
|---|---|---|
| RC.RP — Recovery plan executed | [FILL IN] | [FILL IN: documented recovery steps, tested or untested.] |
| RC.CO — Recovery communication | [FILL IN] | [FILL IN: customer-communication plan during an active incident, if any.] |

---

## Overall maturity summary

| Function | Dominant maturity level |
|---|---|
| Govern | [FILL IN] |
| Identify | [FILL IN] |
| Protect | [FILL IN] |
| Detect | [FILL IN] |
| Respond | [FILL IN] |
| Recover | [FILL IN] |

**Honest bottom line** (fill in your own — don't copy this line verbatim,
write the sentence that's actually true for {{COMPANY_NAME}}):
[FILL IN]

---

*Template version 1.0, adapted from the NIST CSF self-assessment structure
originally built for the ResponsibleAI Governance Platform
(`compliance/NIST_CSF_SELF_ASSESSMENT.md` in that project) — see
`compliance/COMPLIANCE_STARTER_KIT_OFFER.md` for how this template was
produced and how to get help filling it in.*
