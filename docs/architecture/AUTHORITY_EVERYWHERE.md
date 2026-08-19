# Authority Everywhere — Target Architecture (Phases 1–2)

Last reviewed: 2026-08-19 · Platform version: 1.2.3 · Author: solo maintainer
Status: **design document, not yet implemented**. Nothing described past the
"Today" columns below exists in code. Do not cite this document as evidence
of a shipped capability.

This is Phases 1 and 2 of `docs/strategy/AUTHORITY_EVERYWHERE_MIGRATION.md`'s
40-phase plan, following on from
[`docs/strategy/AUTHORITY_EVERYWHERE_CURRENT_STATE.md`](../strategy/AUTHORITY_EVERYWHERE_CURRENT_STATE.md)
(Phase 0's classification of every existing subsystem). This document does
not replace `SPEC.md` and `SPEC.md` is not being removed — per the
migration plan's own Phase 2 instruction, the two coexist until a deliberate
migration decision is made. `SPEC.md` documents WhitePact's current, shipped
runtime governance core. This document describes the direction that core is
being extended toward.

## Phase 1 — Lock the category

**WhitePact's category is machine authority, not "AI governance."** AI
governance is the current, narrowest expression of a broader problem: any
time a principal (a person or an organization) delegates the ability to act
to something that isn't a person — a script, an LLM agent, a workflow, a
service account — something has to answer "was this action actually
authorized, by whom, under what constraint, and can that be proven after
the fact." Today WhitePact answers that question for one kind of actor (LLM
agents) acting through one kind of channel (MCP tool calls). The category
it belongs to is larger than that, and the architecture needs to be honest
about the difference between "the category we're in" and "the surface
we've built so far."

### The fundamental object is `Action`, not `MCP tool call`

Every one of WhitePact's existing decision primitives is already,
concretely, indifferent to *how* an action arrives — `governance/models.py`'s
`ActionRequest` takes an action name, a target, a value, and a context; the
policy engine, the ceiling, the workflow-sequence rules, and the evidence
chain all operate on that shape, not on anything MCP-specific
(`AUTHORITY_EVERYWHERE_CURRENT_STATE.md`, "Action/decision core" row). MCP
enters only at the edges — `mcp/server.py` translates an incoming MCP tool
call into an `ActionRequest`, and `governance/upstream_executor.py`
translates an authorized `ActionRequest` into an outbound MCP proxy call.
Phase 1's job is to make that boundary explicit and hold it, not to build
anything new:

- **`Action` is the canonical, protocol-agnostic object.** It has an actor,
  an intent, a target, a value/scope, and a context. Nothing in the
  authority-evaluation path (policy, risk, ceiling, workflow, evidence) may
  ever import or depend on an MCP type.
- **MCP is the first adapter, kept exactly where it is.** `mcp/server.py`,
  `mcp/tools.py`, `mcp/governance_integration.py` stay real, working, and
  unchanged in role: one translation layer from a specific wire protocol
  into `Action`, no different in kind from any adapter that doesn't exist
  yet.
- **Framework adapters already prove the pattern generalizes.**
  `integrations/langchain_middleware.py`, `langgraph_gate.py`,
  `adk_toolset.py`, and `a2a_adapter.py` already sit on top of a
  framework-agnostic `TrustClient` rather than talking to the governance
  core directly (Phase 0, "Framework adapters" row) — that is the adapter
  shape every future integration should copy.

### Adapters architected for, not built now

The following are explicitly **future adapter surfaces**, named here so
that `Action`'s schema and the adapter interface are designed with room for
them — and just as explicitly **not being built in this phase or any phase
before its own turn in the 40-phase sequence**:

| Future adapter | What it would translate | Status |
|---|---|---|
| REST / generic HTTP API calls | An outbound API request an agent wants to make | Not started |
| GraphQL mutations | A GraphQL operation an agent wants to execute | Not started |
| Database operations | A direct DB write/DDL an agent or service wants to run | Not started |
| Cloud control-plane calls (AWS/GCP/Azure APIs) | An infrastructure-changing API call | Not started |
| SaaS APIs (Salesforce, Slack, GitHub, etc.) | A third-party platform action | Not started |
| Payment/financial rails | A funds-movement or billing action | Not started |
| Agent-to-agent (A2A) protocol messages | A cross-agent delegation or task handoff | `a2a_adapter.py` exists as a framework adapter (trust-check only) — full `Action`-level A2A adapter not started |
| Message queues / event buses | An async action published for later execution | Not started |
| Enterprise workflow engines (BPM, RPA) | A step in an orchestrated business process | Not started |

**Explicitly out of scope for the Authority Everywhere thesis, now or in
any near-term phase**: robotics/physical actuation, IoT/OT (industrial
control systems), and quantum computing control planes. These are real
categories of "machine authority" in the abstract, but building for them
now would be designing against requirements nobody has stated and no
adapter exists to validate against — a violation of the project's own
no-speculative-abstraction discipline. If a real adapter need arises later,
it gets its own phase, its own threat model, and its own decision to
extend `Action`'s schema — not a pre-built hook sitting unused today.

### Verdict — Phase 1

| Field | Value |
|---|---|
| Phase | 1 — Lock the Category |
| Implementation | Documentation only — confirms `Action` (already implicit in `governance/models.py`) as the fundamental object; no code changed |
| Tests | N/A — no behavior changed |
| Security tests | N/A |
| Ruff / Mypy | N/A (no code touched) |
| Coverage | N/A |
| Threat model | N/A — this phase changes no attack surface |
| Docs | This document, Phase 1 section |
| Backward compatibility | Fully preserved — no interface changed |
| Enterprise value | 3/10 — a prerequisite for later phases' value, not value on its own |
| Differentiation | 2/10 — a naming/scoping decision, not a capability |
| Revenue relevance | 1/10 |
| Architecture fit | 9/10 — matches what the code already does; this phase mostly *observes and names* the existing boundary |
| Remaining weaknesses | The category lock is a decision, not an enforcement mechanism — nothing today prevents a future PR from adding an MCP-specific dependency into the policy/risk/evidence path. A lint rule or architecture test enforcing "no MCP imports in governance/*" would make this durable; not built in this phase. |
| VERDICT | **MOVE TO NEXT PHASE** |

## Phase 2 — The canonical Authority Everywhere execution lifecycle

### Naming collision resolution (blocking, from Phase 0)

Phase 0 flagged a real, already-shipped naming collision: `trust/passport.py`,
`trust/score.py`, and the public `/api/trust-index/*` API already use
"Trust Passport" / "Trust Index" for **AI model** certification (does this
LLM meet a bias/robustness/fairness bar). The target architecture below
needs two other, unrelated concepts that would naturally reach for the same
words: a *principal's* delegated authority, and a *tool/server's*
reputation. Resolved here, before either new concept is named for real
anywhere in code or docs:

| Concept | Scores/certifies | Name used going forward | Status |
|---|---|---|---|
| Existing, public, shipped | An AI **model's** measured bias/robustness/fairness | **Model Trust Index** (API path `/api/trust-index/*` unchanged — no breaking change) | Real, shipped |
| New — Phase 5 | A **principal's** delegated, scoped authority to act | **Authority Passport** | Design only, this document |
| New — Phase 8 | An MCP **tool/server's** trust reputation and incident history | **Tool Trust Network** | Design only, this document |

This is a naming convention for future work, not a code change: no files
are renamed in this phase. When Phase 5 and Phase 8 begin, they use
`AuthorityPassport` and `ToolTrustNetwork`/equivalent as their actual type
names from the start, so the collision never gets built into code. If the
public `/api/trust-index/*` naming itself ever needs to change, that is its
own future, deliberate, deprecation-windowed migration — not something
this document schedules.

### The canonical lifecycle

```
VERIFIED PRINCIPAL
       │  (who is asking — a human, an org, or a machine identity)
       ▼
INTENT CONTRACT
       │  (what they say they want done, and the bounds they're stating up front)
       ▼
AUTHORITY PASSPORT
       │  (what authority they actually hold — scoped, revocable, provable)
       ▼
DELEGATION GRAPH
       │  (has this authority been handed down through a chain, and does
       │   every link satisfy CHILD AUTHORITY ⊆ PARENT AUTHORITY?)
       ▼
AGENT / MACHINE
       │  (the actor that will actually execute — LLM agent, script, service)
       ▼
CAUSAL INFLUENCE ANALYSIS
       │  (what upstream content — memory, tool output, sub-agent result —
       │   causally shaped this specific action, and was any of it untrusted?)
       ▼
TARGET / TOOL TRUST
       │  (is the destination — MCP tool, API, database — itself trustworthy
       │   enough for this action, independent of who's asking?)
       ▼
POLICY + RISK + WORKFLOW
       │  (deterministic rule evaluation: allowed value/target ceilings,
       │   risk tier, and "individually fine, collectively forbidden" sequences)
       ▼
EXECUTION PERMIT
       │  (a single-use, digest-bound authorization to perform exactly
       │   this action and no other)
       ▼
JIT CREDENTIAL
       │  (a just-in-time, narrowly scoped credential minted for this permit,
       │   not a standing credential the agent holds indefinitely)
       ▼
REAL ACTION
       │  (the actual side-effecting call — via whichever adapter: MCP today,
       │   others later)
       ▼
OUTCOME OBSERVATION
       │  (what actually happened — success, failure, partial, unexpected effect)
       ▼
RECONCILIATION
       │  (does the observed outcome match what the permit authorized?)
       ▼
ATTESTATION
       │  (a signed statement that this whole chain happened as described)
       ▼
EVIDENCE BUNDLE
       (the durable, queryable record tying every stage above together)
```

### Stage-by-stage: today vs. target

Each row states what exists in the codebase right now (per Phase 0's
classification) and what the target primitive adds. "Today" entries are
factual claims about existing code; "Target" entries are design intent,
not implemented.

| # | Stage | Today (real, shipped) | Target (this phase's design, not yet built) |
|---|---|---|---|
| 1 | Verified Principal | `auth/oidc.py`, `auth/saml.py`, `auth/mfa.py` — real OIDC/SAML signature verification, weak-key rejection, TOTP MFA. Covers the enterprise-IdP case. | Add W3C Verifiable Credentials / OpenID4VP support and a `PrincipalClaim`/`EvidenceIssuer` model so a principal can be a *non-human* verified identity (a service account, another organization's attested agent) — additive to the existing IdP path, not a replacement. |
| 2 | Intent Contract | No dedicated object today — an `ActionRequest` states what's being done, not what was promised up front. | A structured `IntentContract`: the stated goal, its declared bounds (max value, allowed targets, time window), captured *before* any action executes, so later stages can check "does this action still match what was promised," not just "is this action individually allowed." |
| 3 | Authority Passport | `governance/ceiling.py`'s `OrgAuthorityCeiling` (max value, allowed/denied targets, delegation depth) is a real subset of this. | Generalize the ceiling into a portable, provable `AuthorityPassport` — issued to a principal, scoped, revocable, independently verifiable (not just an in-process object) — see naming resolution above. |
| 4 | Delegation Graph | `governance/delegation.py` + `db/delegation_repository.py`'s `validate_attenuation()` already enforces `CHILD AUTHORITY ⊆ PARENT AUTHORITY` with tested escalation rejection (`DelegationEscalationError`). This *is* a working delegation graph today. | Package it as a first-class graph queryable independent of a single decision (who delegated to whom, transitively, right now) rather than only checked pairwise at decision time. |
| 5 | Agent / Machine | MCP adapter (`mcp/server.py`) is the only populated adapter today. | No new primitive — this stage *is* Phase 1's adapter boundary. Whatever adapter is active hands off an `Action` here. |
| 6 | Causal Influence Analysis | `governance/memory_firewall.py` — a real, working, but narrow prototype: regex-based detection of persistent-memory injection patterns only. | Generalize to provenance/taint tracking across tool parameters and sub-agent task outputs, not just memory — Phase 7 of the full plan. Not attempted here. |
| 7 | Target / Tool Trust | `governance/upstream.py`, `upstream_discovery.py`, `upstream_executor.py`, `supplychain/scanner.py` — real SSRF-guarded proxying and destination validation exist today. | Continuous trust scoring, tool fingerprinting, and incident-history-linked reputation for MCP tools/servers — "Tool Trust Network" per the naming resolution above. Phase 8 of the full plan. Not attempted here. |
| 8 | Policy + Risk + Workflow | `governance/policy.py` (first-match-wins `Policy`), `risk.py` (`TOOL_RISK_TIERS`), `governance/workflow.py` (`WorkflowSequenceRule` — already implements "individually allowed, collectively forbidden" ordered-subsequence matching). All real, tested, shipped. | No replacement needed — this is the deterministic-controls foundation a future Policy Compiler would compile *from*, per Phase 0's assessment. |
| 9 | Execution Permit | `governance/execution.py`'s `ExecutionAuthorization` — digest-bound, single-use, with real replay protection (`AuthorizationAlreadyConsumedError`, `AuthorizationActionMismatchError`). | Extend with JIT credential binding and a tool-fingerprint field — the mutation/replay properties Phase 10 needs already exist; this is extension, not a rebuild. |
| 10 | JIT Credential | Does not exist. Today's model assumes the executor already holds whatever credential it needs. | A credential broker that mints narrowly-scoped, time-boxed credentials per Execution Permit, so no agent holds a standing broad credential. Phase 10/11 of the full plan. |
| 11 | Real Action | `governance/upstream_executor.py` performs the actual proxied MCP call today. | Same role, any adapter — no change to this stage's contract. |
| 12 | Outcome Observation | Partially real: webhook delivery (`webhooks/manager.py`) can notify on decisions, but there's no structured "what actually happened" capture distinct from "what was authorized." | A structured outcome record captured after execution, independent of the permit that authorized it. |
| 13 | Reconciliation | Does not exist. | Compare Outcome Observation against the Execution Permit / Intent Contract — did the action stay within what was actually promised and authorized. |
| 14 | Attestation | Sigstore/`actions/attest-build-provenance` exists for *release artifacts* (a different concern — see `compliance/SIGNED_VERSION_TAGS.md`), not for individual runtime actions. | A signed statement over a completed Principal→...→Reconciliation chain for a single action, analogous in spirit to release attestation but scoped to runtime decisions. |
| 15 | Evidence Bundle | `governance/evidence.py`, `evidence_bundle.py`, `db/evidence_repository.py` — real, tested, hash-chained `EvidenceRecord`, currently scoped to a single decision. | Extend the existing hash chain to cover the full Principal→...→Attestation chain per action, not just the policy decision — per Phase 0's "KEEP, then REFACTOR" assessment. Phase 15 of the full plan. |

### What this phase does not do

Consistent with the plan's own "no automatic progression" rule and Phase
0's explicit list of what it didn't do:

- Does not implement `IntentContract`, `AuthorityPassport`, a generalized
  Causal Influence Firewall, Tool Trust Network, JIT Credential Broker,
  Reconciliation, or per-action Attestation. All remain design-only.
- Does not rename or touch the existing public `/api/trust-index/*` API,
  `trust/passport.py`, or `trust/score.py` — the naming resolution above is
  a forward-looking convention for new code, not a migration of existing
  code.
- Does not remove, deprecate, or restructure `SPEC.md`.
- Does not modify `governance/*`, `mcp/*`, `auth/*`, `trust/*`, or any
  other runtime module — this phase is `docs/architecture/AUTHORITY_EVERYWHERE.md`
  and this section of the strategy doc only.
- Does not begin Phase 3 (Verified Principal implementation) or any later
  phase.

### Verdict — Phase 2

| Field | Value |
|---|---|
| Phase | 2 — Canonical Authority Graph |
| Implementation | This document only — `docs/architecture/AUTHORITY_EVERYWHERE.md`. No runtime code changed. |
| Tests | N/A — no behavior changed |
| Security tests | N/A |
| Ruff / Mypy | N/A (no code touched) |
| Coverage | N/A |
| Threat model | N/A — this phase changes no attack surface; each future implementation phase gets its own threat model per the plan's per-phase deliverable requirement |
| Docs | This document; naming-collision resolution recorded for Phase 5/8 to follow |
| Backward compatibility | Fully preserved — `SPEC.md` untouched, public `/api/trust-index/*` untouched, no code changed |
| Enterprise value | 4/10 — a coherent story to show a design partner, not a capability they can use yet |
| Differentiation | 5/10 — the lifecycle framing itself (delegation-graph-checked, single-use, reconciled, attested machine actions) is a real differentiator once built; today it's a documented intent, which is worth less |
| Revenue relevance | 2/10 — no new sellable surface yet |
| Architecture fit | 8/10 — every "Today" cell above is a real, verified existing module; the design was built by generalizing what's there, not invented from nothing |
| Remaining weaknesses | This is a design document with no enforcement: nothing stops future code from drifting from this lifecycle shape. No architecture tests exist yet to keep the adapter boundary or the naming convention honest over time — worth a lightweight lint/test in an early implementation phase rather than trusting the document alone. |
| VERDICT | **MOVE TO NEXT PHASE, WITH A CAVEAT**: Phase 3 (Verified Principal — Verifiable Credentials / OpenID4VP) is the first phase that touches real code. Recommend confirming with the founder which of Phase 3–8 has the highest near-term revenue relevance (per the enterprise-readiness assessment already given) before defaulting to strict numeric order — the plan permits reordering by business priority, not just proceeding 3, 4, 5... automatically. |

---

**Next**: per the plan's own gating, Phase 3 does not begin until this
document's verdict is reviewed. Recommended focus, restated from the
enterprise-readiness assessment: prioritize the phases with direct
revenue/design-partner relevance (Execution Permit extension, Tool Trust
Network) over completing the full principal-identity generalization first,
since the identity path already has a working enterprise-grade
implementation (OIDC/SAML/MFA) and the permit/tool-trust paths are where a
real design partner would feel the difference soonest.
