# WhitePact — Authority Everywhere: Current State (Phase 0)

Last reviewed: 2026-08-19 · Platform version: 1.2.3 · Author: solo maintainer

This is Phase 0 of `docs/strategy/AUTHORITY_EVERYWHERE_MIGRATION.md`'s
40-phase plan: read the current architecture before designing anything
new, and classify every existing subsystem. Nothing in this document
implements new capability — it is an honest inventory, not a pitch.

## How to read the classifications

- **KEEP** — directly usable as-is in the target architecture, no
  rename or rework needed to serve its role in the new pipeline.
- **REFACTOR** — the concept is right, the implementation needs
  broadening/restructuring to match the target primitive.
- **ABSORB INTO AUTHORITY LAYER** — an early, narrower version of a
  target primitive already exists; the target primitive generalizes it
  rather than replacing it outright.
- **DEPRECATE / RENAME** — creates a real conflict with the target
  architecture (see the naming collision below) and needs a decision
  before Phase 5/8 can proceed without confusion.
- **ENTERPRISE-ONLY CANDIDATE** — a real capability that belongs in the
  commercial tier per the Phase 22 packaging split, not the open-source
  core.
- **INTELLIGENCE ENGINE** — real, useful, but supporting signal, not
  part of the Principal→Intent→Authority→Influence→Trust→Execution→
  Outcome→Evidence identity per Phase 33's own filter.
- **ADAPTER** — a protocol/platform-specific binding onto the canonical
  `Action` model; expected to multiply (REST, A2A, LangChain, etc.), not
  something the core depends on.
- **LEGACY COMPATIBILITY** — a real, separate product line bundled in
  the same repository/package that the Authority Everywhere thesis does
  not require touching.

## Subsystem classification

| Subsystem | Files | Classification | Notes |
|---|---|---|---|
| Action/decision core | `governance/models.py`, `gateway.py` | **KEEP** | `ActionRequest`/`AgentContext`/`AuthorityContext`/`DecisionResult` map directly onto the target's canonical `Action` object; `WhitePactRuntimeGateway` is already the deterministic, DB-free evaluator the target architecture wants. |
| Delegation Graph | `governance/delegation.py`, `db/delegation_repository.py` | **KEEP** | `validate_attenuation()` already enforces "child authority ⊆ parent authority" (Phase 5's core invariant) with real escalation rejection, tested. This *is* a working Delegation Graph, just not yet packaged as `AuthorityPassport`. |
| Authority ceiling | `governance/ceiling.py` | **KEEP** | `OrgAuthorityCeiling` (max value, allowed/denied targets, delegation depth) is a real subset of what `IntentContract` (Phase 4) needs to express. |
| Policy engine | `governance/policy.py`, `risk.py` | **KEEP** | First-match-wins `Policy` + static `TOOL_RISK_TIERS` are the deterministic-controls foundation the Policy Compiler (Phase 6) would compile *from* — not something to replace. |
| Workflow sequences | `governance/workflow.py` | **KEEP** | `WorkflowSequenceRule` already implements exactly Phase 12's "individually allowed, collectively forbidden" requirement (ordered-subsequence matching in a time window). This phase is substantially pre-built. |
| Execution binding | `governance/execution.py`, `approval.py` | **KEEP** | `ExecutionAuthorization`/`ApprovalRequest` already have real digest-based mutation detection and single-use replay protection (`AuthorizationAlreadyConsumedError`, `ApprovalActionMismatchError`) — the exact properties Phase 10's `ExecutionPermit` asks for. Needs extending (JIT credential binding, tool fingerprint field) not rebuilding. |
| Evidence chain | `governance/evidence.py`, `evidence_bundle.py`, `db/evidence_repository.py` | **KEEP, then REFACTOR** | Hash-chained `EvidenceRecord` is real and tested. Currently records a single decision, not the full Principal→Intent→Authority→…→Attestation chain Phase 15 wants — extension, not replacement. |
| Memory Firewall | `governance/memory_firewall.py` | **ABSORB INTO AUTHORITY LAYER** | This is a narrow, working prototype of the **Causal Influence Firewall** (Phase 7) — but scoped only to persistent-memory injection patterns via regex, not general provenance/taint tracking across tool parameters and sub-agent tasks. Phase 7 generalizes this; it does not start from zero. |
| MCP Upstream Gateway | `governance/upstream.py`, `upstream_discovery.py`, `upstream_executor.py`, `supplychain/scanner.py` | **ABSORB INTO AUTHORITY LAYER** | Real SSRF-guarded proxying and tool discovery already exist. This is the seed of the **Tool Trust Network** (Phase 8) and **Schema Mutation Lock** (Phase 9) — currently does destination validation only, no continuous trust scoring, fingerprinting, or incident history. |
| Identity/auth | `auth/oidc.py`, `auth/saml.py`, `auth/mfa.py`, `auth/crypto_policy.py` | **KEEP** | Real OIDC/SAML verification with signature checks, weak-key rejection, MFA — this is the enterprise-IdP leg of **Verified Principal** (Phase 3). Missing: W3C Verifiable Credentials / OpenID4VP / claim-class modeling (`PrincipalClaim`, `EvidenceIssuer`) — additive, not a rewrite of what exists. |
| RBAC / org model | `rbac/models.py`, `permissions.py`, `db/org_repository.py` | **KEEP** | Foundational identity/org substrate every later phase depends on. |
| MCP adapter | `mcp/server.py`, `tools.py`, `resources.py`, `governance_integration.py` | **KEEP as PRIMARY ADAPTER** | Per Phase 1, MCP must not become the fundamental object — and it currently *is* the only adapter. Real, working, and should stay exactly where it is: one adapter among several, not the core. |
| Framework adapters | `integrations/langchain_middleware.py`, `langgraph_gate.py`, `adk_toolset.py`, `a2a_adapter.py`, `client.py` | **ADAPTER** | Already structured as adapters onto a framework-agnostic `TrustClient` — matches the target multi-adapter shape directly. |
| REST/dashboard surface | `dashboard/app.py`, `middleware.py` | **KEEP, ENTERPRISE-ONLY CANDIDATE (control-plane pieces)** | The API surface itself (RBAC-gated REST) is core-adapter material. Admin/org-management UI pieces (billing, webhook config UI, multi-tenant org admin) are natural candidates for the Phase 22 **Enterprise control plane**, not the open-source core. |
| Webhooks | `webhooks/manager.py`, `models.py` | **KEEP** | SSRF-guarded outbound delivery is real, tested infrastructure — a delivery mechanism Outcome Attestation (Phase 13) can notify through, not the reconciliation logic itself. |
| Incident database | `incidents/logic.py`, `db/incident_repository.py`, `db/public_incident_repository.py` | **KEEP, REPOSITION** | Currently a standalone public feature (community-reported incidents). Real overlap with Phase 8's incident tracking for tool trust — worth connecting rather than duplicating when Phase 8 starts. |
| **Trust Passport / Trust Index** | `trust/passport.py`, `score.py`, `badge.py`, public `/api/trust-index/*` routes | **NAMING COLLISION — see below** | Scores **AI models** (an LLM's fairness/bias/robustness), already publicly shipped under the name "Trust Passport"/"Trust Index". This is a *different concept* from Phase 5's `AuthorityPassport` (grants/scopes a *principal's* authority) and Phase 8's Tool Trust Network (scores *MCP tools/servers*). Real, found-not-fabricated conflict — flagged as this phase's bug, not silently worked around. |
| Guardrails / hallucination / red team | `guardrails/engine.py`, `hallucination/detector.py`, `redteam/simulator.py` | **INTELLIGENCE ENGINE** | Real, deterministic-first PII/toxicity/hallucination signal generators — useful as inputs to Causal Influence and Trust scoring later, but per Phase 33's own filter, they don't define WhitePact's identity and should not be allowed to. |
| Cost/eval/leaderboard | `cost/`, `eval/`, `leaderboard/` | **INTELLIGENCE ENGINE** | Real, working, genuinely useful — but orthogonal to the Principal→…→Evidence chain. Same Phase 33 treatment as above: keep, don't let them drive roadmap priority. |
| PrivacyLabel | `src/privacylabel/` (differential privacy, deepfake detection, federated learning) | **LEGACY COMPATIBILITY** | A separate product line bundled in the same package/repo. Does not strengthen any of Principal/Intent/Authority/Influence/Trust/Execution/Outcome/Evidence — Phase 33's filter says don't touch it as part of this thesis. |
| BiasBuster | `src/biasbuster/` (bias probes) | **LEGACY COMPATIBILITY** | Same treatment as PrivacyLabel — a real, separate, bundled product surface, out of scope for Authority Everywhere. |
| `SPEC.md` | — | **KEEP (until deliberate migration)** | Per Phase 2's explicit instruction, not removed. `docs/architecture/AUTHORITY_EVERYWHERE.md` (Phase 2, not yet written) will supplement it, not replace it, until a deliberate migration decision is made. |

## The one real bug this phase found

**Naming/conceptual collision between the existing "Trust Passport" and
the planned `AuthorityPassport` / Tool Trust Network.** The current
`trust/` module and its public API (`GET /api/trust-index/*`,
`compliance/CAIQ_SELF_ASSESSMENT.md` references, the public `/registry`
page) already ship "Trust Passport" as a name for **AI model**
certification. Phase 5 of the target architecture introduces
`AuthorityPassport` for a completely different concept (a *principal's*
delegated authority), and Phase 8 introduces a "Tool Trust Network" for
yet another different concept (MCP *tool/server* reputation). Building
either of those under overlapping naming would confuse both the API
surface and anyone reading the docs — this is a real design conflict,
not a hypothetical one, since the existing name is already public and
depended on.

**Not fixed in this phase** — renaming a public, already-shipped API
(`/api/trust-index/*`) is itself a breaking-change decision that needs
its own migration plan (deprecation window, redirect, changelog entry)
per `RELEASING.md`'s backward-compatibility discipline, not a
find-and-patch done inside a Phase 0 documentation pass. Recorded here
as the concrete P0 blocker Phase 2 (`AUTHORITY_EVERYWHERE.md`) must
resolve before naming `AuthorityPassport`/Tool Trust Network for real:
propose distinguishing names now (e.g. keep "Model Trust Index" for the
existing AI-model concept, reserve "Authority Passport" and "Tool Trust
Network" for the new ones) rather than colliding on "Passport"/"Trust"
across three different objects.

## What Phase 0 did *not* do

- Did not write `docs/architecture/AUTHORITY_EVERYWHERE.md` (Phase 2).
- Did not implement any new primitive (`IntentContract`,
  `AuthorityPassport`, Causal Influence Firewall generalization, Tool
  Trust Network, JIT Credential Broker, Outcome Attestation, etc.).
- Did not run the Phase 27 adversarial test classes against anything
  new, since nothing new exists yet.
- Did not produce `BUSINESS_MODEL.md`, `FIRST_REVENUE_PLAN.md`,
  `MNC_TRUST_MATRIX.md`, or `PLATFORM_MATRIX.md` — those are Phase 23,
  24, 36 deliverables, not Phase 0's.

Per the migration plan's own rule ("No automatic progression — do not
start the next phase until the previous phase has a written verdict"),
those come after this classification is reviewed, not folded into it.
