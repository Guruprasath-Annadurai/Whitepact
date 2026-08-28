# Phase 15 — Enterprise Trust + Procurement Readiness: Design

## Objective

Per the master directive's Phase 15 ("Enterprise Trust + Procurement
Readiness"). Per directive rule 63: audit first. Unlike Phases 8-14,
this phase's subject matter is inherently more documentation-facing
than code-facing — procurement readiness *is* the set of artifacts an
enterprise security team reads before approving a vendor, not a
runtime property a unit test exercises.

## Audit: what already exists

This platform's procurement-readiness posture is, on inspection,
extraordinary for a solo-maintained project — `compliance/` alone
contains: `SOC2_READINESS.md`, `SOC2_ALTERNATIVE_PATH.md`,
`CAIQ_SELF_ASSESSMENT.md` (+ the completed CAIQ v4.0.3 spreadsheet),
`NIST_CSF_SELF_ASSESSMENT.md`, `DPA_TEMPLATE.md` +
`DPA_ATTORNEY_SCOPE_BRIEF.md`, `VENDOR_RISK_ASSESSMENT.md`,
`INCIDENT_RESPONSE_RUNBOOK.md`, `TABLETOP_EXERCISE_2026-07-21.md`,
`KEY_MANAGEMENT.md`, `PROJECT_CONTINUITY_PLAN.md`,
`SIGNED_VERSION_TAGS.md`, three `OPENSSF_*` evidence/gap-analysis
documents, `INTERNAL_SECURITY_REVIEW.md`, `INSURANCE_PARTNERSHIP_PITCH.md`.
At the repository root: `SECURITY_ASSURANCE_CASE.md` (911 lines — a
full threat model, trust-boundary map, and 12-row evidence matrix
mapping each security claim to its control, implementation, test, and
CI check), `ENTERPRISE_SECURITY.md`, `SECURITY.md`, `SLA.md`,
`GOVERNANCE.md`. This is, in substance, already comprehensive
procurement-readiness documentation — not a gap to build from
scratch.

**The document's own §8 "Known Limitations" is itself the honest,
external-gate-style accounting** the master directive's "no false
claims" rule asks for: no independent pentest, no SOC 2/ISO 27001
certification, encryption-at-rest not guaranteed for every deployment
mode, several controls opt-in rather than default-on, named and stated
plainly rather than implied to be handled.

## The genuine gap: staleness, not absence

`SECURITY_ASSURANCE_CASE.md` states "Last reviewed: 2026-08-19 ·
Platform version: 1.2.2" — nine days before this directive's own
Phases 11 and 13 shipped real, tested improvements the document's
Evidence Matrix (§7) doesn't yet reflect:

- **C4** ("Runtime authority enforcement") cites only
  `InternalToolExecutor`/`tests/test_executor_bypass_invariant.py`.
  Phase 11 proved the identical property for `UpstreamMCPExecutor`
  (`tests/test_citadel_execution_containment.py`,
  `tests/test_upstream_gateway.py`) — the claim "only covers this
  platform's own MCP dispatch path" residual note is now narrower than
  reality.
- **C6** ("Execution Permit/approval binding") cites
  `compute_action_digest` and the consumed-flag only. Phase 11's
  audit confirmed target-fingerprint drift detection
  (`AuthorizationTargetDriftError`) is real, additional binding beyond
  digest+consumed-flag, with its own dedicated adversarial tests.
- **C11** ("Hash-chain tamper-evidence") states the residual limitation
  ("does not detect full-chain recompute by an attacker with DB write
  access") with no mention that a mitigating mechanism
  (`governance/evidence_bundle.py`'s offline-verifiable, digest-bearing
  export) exists and is now proven, by Phase 13's own tests, to detect
  exactly that.

The document's own header explicitly invites this: "Update this
assurance case whenever a new transport, auth mechanism, governance
primitive, or supply-chain control ships — the same day, not
'eventually.' A stale assurance case that implies coverage it doesn't
have is worse than an honestly incomplete one." A stale assurance case
also understates real, already-verified coverage — the mirror-image
problem, equally worth fixing for an artifact enterprise buyers rely
on to assess this platform accurately.

## Scope for this phase

Update `SECURITY_ASSURANCE_CASE.md`:
1. §7 Evidence Matrix rows C4, C6, C11 — add the Phase 11/13 test
   files and, for C11, note the mitigating mechanism alongside the
   still-real limitation (no *automated* periodic external
   publication exists — the mechanism is real, the pipeline around it
   isn't, exactly Phase 13's own honest framing).
2. Bump "Last reviewed" date and platform version reference.

No source code changes. No new tests (nothing new to regression-test —
this phase corrects references to evidence Phases 11/13 already
produced). No database migration.
