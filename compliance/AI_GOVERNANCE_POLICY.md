# WhitePact AI Governance Policy

**Owner:** Founder / Maintainer  
**Effective when merged:** 2026-08-27  
**Review cadence:** at least annually and on material AI, architecture, provider, regulatory or incident change.

## Purpose and scope

This policy governs WhitePact's own AI-related functionality, agent/tool governance paths, human-approval workflows, evidence, model integrations and AI assurance features. It does not extend WhitePact's authority beyond `ENFORCEMENT_BOUNDARY.md` and does not claim independent certification.

WhitePact is scoped primarily as an **Orchestrated Service Provider (OSP)** and secondarily as an **Application Provider (AP)**. It is not a Model Provider in the current assessed scope because it does not train or distribute foundation models.

## Shared responsibility

Out of WhitePact's direct control unless explicitly implemented/documented are third-party model training and weights, provider infrastructure/retention, customer-authored prompts and agent code outside inline WhitePact paths, physical/cloud infrastructure for self-hosting, and actions outside documented enforcement boundaries.

## Governance principles

1. Core authorization/governance decisions remain deterministic rather than silently delegated to an LLM.
2. Delegated authority must not exceed parent authority; organization ceilings may further restrict it.
3. Material risk may escalate to a real `REQUIRE_APPROVAL` state and human resolution path.
4. Evidence-critical governed execution fails closed when required evidence cannot be recorded.
5. Inline, voluntary, opt-in and external boundaries must be documented honestly.
6. Governance evidence should minimize raw sensitive argument data.
7. Decisions should be traceable and tamper-evident within documented hash-chain limits.
8. Self-assessments and mappings must never be represented as independent certification.

## AI risk management

AI risks are reviewed through the quarterly process in `GOVERNANCE.md` and the technical process in `THREAT_MODEL.md`. Material triggers include new model providers, autonomous tool categories, persistent-memory behavior, A2A connectivity, enforcement boundaries, approval semantics, trust inputs, incidents/near misses, or applicable legal/contractual change.

## Human oversight and autonomy

`REQUIRE_APPROVAL` provides a real pending/approved/denied workflow. Autonomy-budget controls can limit sustained unsupervised activity where configured. The concurrent-burst limitation documented in `ENFORCEMENT_BOUNDARY.md` remains an open risk and must not be described as a hard concurrency-safe ceiling until fixed.

## Agent, tool and prompt security

WhitePact uses organization/identity scoping where supported, explicit tool risk classification, attenuated/revocable delegation, evidence recording, applicable SSRF/trust protections, and persistent-memory injection scanning. WhitePact is **not** a universal OS/container/network sandbox for external tools/plugins.

WhitePact scans defined persistent-memory injection patterns but does not universally control the separation of system/developer/user prompts inside third-party model runtimes. Those controls remain customer/provider responsibility where outside WhitePact's runtime boundary.

## Provider governance

Third-party model providers are suppliers. Their training-data provenance, model-weight protection, retention/training policies, abuse monitoring and infrastructure resilience are not WhitePact controls unless explicitly contracted/implemented. Provider certifications must not be inherited as WhitePact certifications.

## Inventory, change control and testing

Material AI functionality is inventoried in `AI_SYSTEM_INVENTORY.md`, `README.md`, `ARCHITECTURE.md`, `MACHINE_AUTHORITY_V1.md`, `ENFORCEMENT_BOUNDARY.md` and `THREAT_MODEL.md`. Changes follow PR/CI controls and should update affected risk/boundary evidence.

Current assurance includes tests, coverage gates, static analysis, dependency/secret scanning, signed releases, SBOMs and provenance. These are self-managed; AI-CAIQ questions requiring **independent** assurance must be answered accordingly.

## AI incidents

AI-related incidents include unauthorized autonomous execution, policy/approval bypass, harmful context injection resulting in action, cross-tenant exposure, compromised AI/tool supply chain, material evidence-integrity failure, or material unsafe/bias/drift failures where WhitePact controls were expected to operate. Handle them under `compliance/INCIDENT_RESPONSE_RUNBOOK.md` and update affected tests/policies/threat models after review.

## External claims

After publication, a permissible Level 1 claim is: "WhitePact is listed in the CSA STAR Registry at STAR for AI Level 1 based on its published AI-CAIQ self-assessment." Do not use `CSA certified` for Level 1, and do not claim SOC 2 or ISO certification without the corresponding independent status.
