# Enterprise Documentation Index

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH
CLOSURE MASTER DIRECTIVE, Phase 31. `00_MASTER_READINESS_AUDIT.md`'s
Documentation row named the gap: the specific consolidated pack the
directive wants (`ARCHITECTURE.md`, `SECURITY_ARCHITECTURE.md`,
`DATA_FLOW.md`, `TENANCY_MODEL.md`, `AUDIT_MODEL.md`,
`KNOWN_LIMITATIONS.md`) doesn't exist as one directory — the
equivalent content is real and thorough, but scattered across many
root-level documents.

**Deliberate choice, stated honestly**: this index does **not** copy
or re-derive that content into six new files. Every one of those docs
already has a single, actively-maintained source of truth elsewhere in
this repository; duplicating them here would create two copies that
drift apart the moment either one is updated — a worse outcome than
the discoverability gap this phase closes. This directory is a
navigation layer, not a second copy.

## The six-document pack, mapped to where it actually lives

| Directive asks for | Lives at | What it actually covers |
|---|---|---|
| `ARCHITECTURE.md` | [`SPEC.md`](../../SPEC.md) | The canonical, current architecture — Identity → Authority → Policy → Risk → Workflow → Decision → Execution Permit → Execution → Evidence pipeline, the governance decision core, and MCP as an adapter on top of it. The root-level [`ARCHITECTURE.md`](../../ARCHITECTURE.md) itself says as much — it predates the authority-layer work and covers only BiasBuster/PrivacyLabel/ResponsibleAI package internals, not the platform as a whole. |
| `SECURITY_ARCHITECTURE.md` | [`ENTERPRISE_SECURITY.md`](../../ENTERPRISE_SECURITY.md) + [`SECURITY_ASSURANCE_CASE.md`](../../SECURITY_ASSURANCE_CASE.md) | `ENTERPRISE_SECURITY.md` answers the questions a security/procurement team asks before approving a vendor (encryption at rest, data residency, audit trail integrity, SSO enforcement) — current fact, not aspiration. `SECURITY_ASSURANCE_CASE.md` is the formal OpenSSF Silver `assurance_case`: threat model, trust boundaries, secure-design argument, common-vulnerability-class argument. |
| `DATA_FLOW.md` | [`SPEC.md`](../../SPEC.md) §2 ("The core pipeline") + §2.5 (the Sovereignty Kernel) | Request → governance evaluation → consent/policy resolution → AuthorityGrant → authorization → execution → evidence, the exact data flow every phase of this branch's own closure work (Phases 1–5, 7) traced and extended. |
| `TENANCY_MODEL.md` | [`SPEC.md`](../../SPEC.md) §5 ("Multi-tenancy and organization boundary") + [`PHASE7_CROSS_TENANT_ISOLATION.md`](../enterprise-readiness/PHASE7_CROSS_TENANT_ISOLATION.md) | SPEC.md states the tenancy model as designed; the Phase 7 doc is the real, adversarial evidence that it holds in practice (including the one place it didn't, found and fixed). |
| `AUDIT_MODEL.md` | [`governance/evidence.py`](../../src/responsibleai/governance/evidence.py)'s module docstring | **Named as a genuine gap, not silently filled**: no dedicated root-level doc describes the hash-chained `EvidenceRecord` audit model end to end — the authoritative description lives only in that module's own docstring (`verify_chain()`'s tamper-detection design, `audit_anchor.py`'s external-anchor architecture). A dedicated `docs/enterprise/AUDIT_MODEL.md` synthesizing that into standalone documentation is a reasonable follow-up this phase didn't do, to avoid producing a summary doc that's really just this document's own untested paraphrase of code it didn't re-verify. |
| `KNOWN_LIMITATIONS.md` | [`DEFINITION_OF_DONE.md`](../../DEFINITION_OF_DONE.md) + every phase evidence doc under [`docs/enterprise-readiness/`](../enterprise-readiness/) | `DEFINITION_OF_DONE.md` is the closing report for the platform's own 29-phase migration, with real/incomplete stated plainly per item. Every phase doc this session produced (`PHASE5_PURPOSE_BINDING.md` through `PHASE24_DOCKERFILE_HARDENING.md`) carries its own "Known limitations"/"What this does not cover" section — collectively the most current, itemized limitations record, more granular than one static file could stay. |

## Everything else produced by this closure work

- [`docs/enterprise-readiness/`](../enterprise-readiness/) — every
  phase's own evidence report (Phases 1–5, 7, 13–19, 24), each with a
  verdict, verification evidence, and known limitations.
- [`docs/operations/`](../operations/) — `INCIDENT_RESPONSE.md`,
  `DR_RESTORE_DRILL.md`.
- [`docs/security/`](../security/) — `DEPENDENCY_RISK_REGISTER.md`,
  `CREDENTIAL_SCOPING_AND_ROTATION.md`,
  `PRODUCTION_CONFIGURATION_STANDARD.md`, `GITHUB_ACTIONS_PINNING.md`.
- [`THREAT_MODEL.md`](../../THREAT_MODEL.md) — threat model for the
  current attack surface.
- [`compliance/`](../../compliance/) — OpenSSF Best Practices / OSPS
  Baseline self-certification evidence, SOC 2 alternative path, project
  continuity plan.

## Trust boundaries

See [`TRUST_BOUNDARIES.md`](TRUST_BOUNDARIES.md) (Phases 32/33) for the
formal diagram of who/what is trusted at each edge of the system — the
properties it documents were already true in code before this phase;
this closes the gap that they weren't drawn anywhere.
