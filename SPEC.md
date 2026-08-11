# WhitePact — Architecture Specification

> **Status of this document**: this is the target architecture contract for
> WhitePact Enterprise Foundation v2. Sections are explicitly marked
> **[TODAY]** (verified against current source, working now) or
> **[TARGET]** (the architecture this spec defines, not yet built). Do not
> read a **[TARGET]** section as a claim that the described component
> exists — per this project's own engineering rules, implementation status
> is never assumed, only what's been inspected in source. See
> `MIGRATION_WHITEPACT_V2.md` (forthcoming) for the phased plan that
> closes the gap between the two.

Last reviewed: 2026-08-11 · Repository: `Guruprasath-Annadurai/Whitepact`
(renamed from `ResponsibleAi`; package identity migration in progress —
see Section 9). Sections 2-3's core entities, a first, deterministic
`WhitePactRuntimeGateway`, risk-tiered routing (Phase 9), and a first
policy engine (Phase 10) now exist in `src/responsibleai/governance/`
(see `MIGRATION_WHITEPACT_V2.md` Section 8) — each affected section
below has been updated in place to say exactly what's real and what
remains **[TARGET]**; none of the original **[TARGET]** markers were
removed wholesale.

---

## 1. What WhitePact is

**WhitePact is not "ResponsibleAI renamed." It is not "27 MCP governance
tools." It is not "an MCP gateway."**

WhitePact is an independent runtime authority, governance, and assurance
layer for autonomous systems.

> AI systems may decide what they want to do. WhitePact determines
> whether they should be allowed to do it.

The distinction that matters:

- **IAM answers**: *"Can this identity access this resource?"* — a
  static, pre-provisioned permission check.
- **WhitePact answers**: *"Should this autonomous action be permitted in
  this context, right now, given who's asking, what's been delegated to
  them, what the action actually is, and what the organization's policy
  says about it?"* — a dynamic, per-action decision.

**[TODAY]**: this project ships as a governance *evaluation* platform —
trust scoring, guardrails (PII/toxicity), hallucination detection, red
teaming, compliance mapping (NIST AI RMF / EU AI Act / ISO 42001), cost
intelligence, drift monitoring, a public leaderboard, a Trust Index, an
AI Incident Database, and 27 MCP tools exposing all of it. All of these
are real, tested, and running (verified: 1349 tests passing, mypy/ruff
clean, CI green on GitHub Actions as of commit `6ffe933`).

**[TARGET]**: WhitePact becomes a runtime decision layer that sits
*between* an agent's proposed action and the enterprise system it would
affect, using the existing evaluation capabilities as the intelligence
behind a five-way decision, not just a report a human reads after the
fact.

---

## 2. The core pipeline **[PARTIALLY TODAY — Phases 8-12]**

```
Organization
  → delegates authority to
Agent (identity + framework + model)
  → proposes
Action (an MCP tool call, an API operation, a transaction, a data export...)
  → evaluated against
Policy (deterministic organizational rules)              [TODAY, first version — Phase 10]
  → informed by
Trust (existing Trust Index / leaderboard signals)        [TODAY, not yet wired in]
  → and
Risk (classified severity of the action)                 [TODAY — Phase 9]
  → produces a
Decision: ALLOW | ALLOW_WITH_REDACTION | REQUIRE_APPROVAL | DENY | QUARANTINE
  → routes to
Execution (the actual MCP/API/SaaS/database call, only if allowed)
  → and always produces
Evidence (an immutable, exportable record of the whole decision) [TODAY, first version — Phase 12]
```

**[TODAY]**: `src/responsibleai/governance/` now has a real, tested
component that takes "agent proposes action" as input and returns one
of the five decisions above as output —
`WhitePactRuntimeGateway.evaluate(action, authority, policy=None)`
(`tests/test_governance_core.py` + `test_governance_risk.py` +
`test_governance_policy.py`, 49 tests across the package). Concretely,
today it checks, in order: (1) does the caller-supplied
`AuthorityContext` grant this action's type at all; (2) risk
classification (`governance/risk.py`) — every action gets a real
`RiskTier`, always recorded on the result; (3) an *optional*
organization `Policy` (`governance/policy.py`) — if supplied and a rule
matches, a `DENY`/`REQUIRE_APPROVAL` effect short-circuits, an `ALLOW`
effect is recorded but doesn't skip the next step; (4) does the
existing, tested `GuardrailsEngine` find PII (→
`ALLOW_WITH_REDACTION`, reusing its own redaction) or
toxicity/custom-pattern matches (→ `DENY`) in any string-valued
argument. A `DecisionResult` can now be turned into a persisted,
hash-chained `EvidenceRecord` (`db/evidence_repository.py`, Phase 12)
and a `REQUIRE_APPROVAL` decision into a persisted, resolvable
`ApprovalRequest` (`db/approval_repository.py`, Phase 11) — both real,
tested (`tests/test_governance_persistence.py`,
`tests/test_governance_api.py`), and exposed via
`/api/governance/evidence`, `/api/governance/evidence/verify`,
`/api/governance/approvals`, and
`/api/governance/approvals/{id}/resolve` in the dashboard API — see
Section 3.7 and MIGRATION_WHITEPACT_V2.md Section 8 for exactly what's
covered. Genuinely still **[TARGET]**: Trust Index signals don't
actually feed into any decision yet (an `AgentContext.trust_state` field
exists but nothing populates or reads it automatically). This gateway is
also not wired into the MCP tool dispatch path yet: `dispatch_tool()` in
`mcp/tools.py` calls tool handlers directly, unchanged; nothing today
constructs an `ActionRequest` from an incoming MCP tool call and routes
it through
`WhitePactRuntimeGateway` first. That wiring is real, separate,
own-tested work, not implied by the gateway existing.

---

## 3. Core entities

### 3.1 Agent **[TODAY — Phase 8]**

An autonomous or semi-autonomous software actor requesting an action.

```
AgentContext:
  agent_id: str                 # stable identifier for this agent instance
  organization_id: str          # tenant boundary — see RBAC below
  identity: IdentityContext     # who/what is actually behind this agent
  framework: str | None         # e.g. "langchain", "langgraph", "adk", "mcp-client"
  provider: str | None          # e.g. "openai", "anthropic", "azure-openai"
  model: str | None             # e.g. "gpt-4o", a customer's Azure deployment name
  trust_state: TrustCheckResult | None  # cached Trust Index result for this agent/tool, if known
  metadata: dict[str, Any]      # framework-specific extras, never secrets
```

**[TODAY]**: `AgentContext` is a real, tested dataclass
(`src/responsibleai/governance/models.py`) — this is verified current
source, not the target shape above restated as a claim. It reuses the
existing `TrustCheckResult` (`src/responsibleai/integrations/client.py`)
for `trust_state` rather than inventing a new `TrustSummary` type, since
`TrustCheckResult` already is exactly "a lookup of a model or tool's
public trust score" and nothing about `AgentContext` needed anything
more. Not yet true: nothing populates `trust_state` automatically —
callers construct it themselves; auto-populating it from a live Trust
Index lookup is unimplemented, real follow-up work.

### 3.2 Identity **[TODAY, partially — Phase 8]**

Who or what is making the request. Must support humans, service
accounts, agents, API keys, OAuth/OIDC identities, and future workload
identities.

**[TODAY]**: `OrgContext` (`src/responsibleai/rbac/models.py`) already
carries `key_id`, `role` (`OWNER`/`ADMIN`/`ANALYST`/`VIEWER`), `org_id`,
and `plan` — this is a real, working, tested identity model, but it's
scoped to *human/API-key* access to the REST API and dashboard, not to
an *agent* acting on a human's or organization's behalf. OIDC/SSO
support exists (`src/responsibleai/auth/` — see `sso` extra in
`pyproject.toml`). MFA (TOTP, RFC 6238) is implemented and tested.

`IdentityContext` (`src/responsibleai/governance/models.py`) now
generalizes `OrgContext` as described — `IdentityContext.from_org_context()`
maps a real `OrgContext` (from a static API key or an OIDC JWT, see
`mcp/server.py`'s `_authenticate`) into the broader vocabulary, without
modifying `OrgContext` itself. What remains genuinely unimplemented: a
workload-identity kind (SPIFFE/SPIRE-style) has no real issuer or
verification path anywhere in this codebase — `IdentityContext.kind`
accepts the string `"workload"`, but nothing produces or validates one
today, so treat that specific kind as aspirational, not working.

### 3.3 Authority **[TODAY, minimal — Phase 8]**

What authority has been delegated to the agent. This is deliberately
**not** the same thing as a raw RBAC role.

- **RBAC/IAM question**: does this API key have the `ADMIN` role, which
  technically permits calling `POST /api/trust-index/certify`?
- **Authority question**: even though this agent's identity *can*
  technically reach that endpoint, has this organization actually
  delegated "certify trust passports" authority to *this specific
  agent*, in *this context* (time of day, transaction value, data
  sensitivity, environment)?

**[TODAY]**: `AuthorityContext` exists
(`src/responsibleai/governance/models.py`) as a minimal, real
implementation: `granted_action_types` (a set the caller supplies —
nothing derives it from RBAC roles automatically yet) and
`require_approval_for`, both enforced by `WhitePactRuntimeGateway`. The
"in *this context*" part of the authority question above — time of day,
transaction value, data sensitivity — is represented only as an open
`constraints: dict[str, Any]` bag; nothing in the gateway actually reads
or enforces those constraints yet. There is still no delegation
*workflow* (an org granting authority to a specific agent through some
UI or API) — callers construct `AuthorityContext` directly in code
today. RBAC roles remain the only authority signal enforced
automatically anywhere in the codebase.

### 3.4 Action **[TODAY — Phase 8]**

A proposed operation an agent wants to execute. Conceptually:

```
ActionRequest:
  action_id: str
  agent: AgentContext
  action_type: str        # "mcp_tool_call" | "api_call" | "transaction" |
                           # "db_operation" | "message_send" | "deployment" |
                           # "approval" | "data_export" | ...
  target: str              # e.g. the MCP tool name, or the API route
  arguments: dict[str, Any]  # sanitized before it ever reaches Evidence storage
  proposed_at: datetime
```

**[TODAY]**: `ActionRequest` is a real dataclass
(`src/responsibleai/governance/models.py`) matching the shape above
exactly. It's a generic abstraction, not yet a *used* one: `dispatch_tool`
in `mcp/tools.py` still dispatches MCP tool calls directly, and nothing
in `mcp/server.py` constructs an `ActionRequest` for an incoming tool
call and routes it through `WhitePactRuntimeGateway` before dispatching.
`arguments` is not yet actually "sanitized before it reaches Evidence
storage" in practice, because there is no Evidence storage yet
(Section 3.7) — the note in the field comment above describes the
target end state, not a guarantee this phase enforces.

### 3.5 Policy **[TODAY, first version — Phase 10]**

Machine-enforceable organizational rules governing actions. The "small,
strongly typed internal model first — not an LLM, not necessarily
OPA/Rego on day one" this section originally called for (see Section 6
below on deterministic vs. probabilistic controls) now exists:
`Policy`/`PolicyRule` in `src/responsibleai/governance/policy.py`. A
`Policy` is an ordered list of `PolicyRule`s, each matching on risk
tier / action type / target and producing an `ALLOW`/`DENY`/
`REQUIRE_APPROVAL` effect; evaluation is first-match-wins, deliberately
with no priority/specificity scoring to explain. This is genuinely the
first, smallest version — no OPA/Rego, no expression language, no rule
persistence (an organization's `Policy` is constructed in code and
handed to `WhitePactRuntimeGateway.evaluate()` per call; there is no
`policies` database table, no API to author or store one, and no UI).
`rai_policy_check` (a separate, existing MCP tool that evaluates text
against blocklists/disclaimers) is unrelated and unchanged by this —
still a real, narrow, working feature, still not this engine.

### 3.6 Decision **[TODAY — Phase 8, QUARANTINE excepted]**

One of exactly five outcomes:

| Decision | Meaning | Status |
|---|---|---|
| `ALLOW` | The action proceeds unmodified. | **[TODAY]** — produced by the gateway when nothing else fires. |
| `ALLOW_WITH_REDACTION` | The action proceeds, but the payload is modified first (e.g. PII stripped) — see `GuardrailsEngine`'s existing redaction logic, which this reuses. | **[TODAY]** — produced when `GuardrailsEngine` finds PII-only findings. |
| `REQUIRE_APPROVAL` | The action is held pending a human (or delegated-authority) approval — see Section 3.7. | **[TODAY]** — produced when the caller-supplied `AuthorityContext.require_approval_for` names the action type (or a matching `Policy` rule says so, Section 3.5); `db/approval_repository.py`'s `ApprovalRepository` now persists it as a resolvable request (`PENDING` → `APPROVED`/`DENIED`, double-resolution rejected), queryable and resolvable via `GET /api/governance/approvals` and `POST /api/governance/approvals/{id}/resolve`. Genuinely still missing: any notification beyond an optional webhook fire, and no automatic re-evaluation or execution of the action once approved — resolving records a human decision, acting on it is the caller's job. |
| `DENY` | The action is blocked outright. | **[TODAY]** — produced on a missing authority grant, or a toxicity/custom-pattern guardrails match. |
| `QUARANTINE` | The action, the agent, or both are held for review beyond a single decision — e.g. an agent exhibiting a pattern of policy violations gets its authority suspended pending investigation, distinct from a single denied action. | **[TARGET]** — a real enum member (`GovernanceDecision.QUARANTINE` exists and is tested as part of the five-way set), but nothing in `WhitePactRuntimeGateway` ever returns it: that requires tracking a *pattern* of violations across requests, which this phase doesn't build. |

`GovernanceDecision` is a real five-way `StrEnum`
(`src/responsibleai/governance/models.py`), replacing what used to be
true of every decision-shaped output in this codebase — binary
(`GuardrailsEngine.scan()` still returns `is_blocked: bool` at its own
layer; `GovernanceDecision` is a layer above it, not a replacement for
it).

### 3.7 Evidence **[TODAY, first version — Phase 12]**

Immutable, tamper-evident structured evidence for every decision.
Conceptually (this is the *target* shape; see below for what's actually
implemented against it):

```
EvidenceRecord:
  evidence_id: str
  organization_id: str
  request_id: str
  agent_id: str
  human_identity: str | None       # the ultimate human/service accountable
  model: str | None
  provider: str | None
  mcp_server: str | None
  tool_or_action: str
  sanitized_arguments_metadata: dict[str, Any]  # never raw secrets
  authority_used: str
  policies_evaluated: list[str]
  trust_signals: dict[str, Any]
  deterministic_checks: dict[str, Any]
  probabilistic_checks: dict[str, Any]
  risk_classification: str
  decision: GovernanceDecision
  reason_codes: list[str]
  approval: ApprovalRecord | None
  timestamps: dict[str, datetime]
  execution_result_metadata: dict[str, Any] | None
  prev_hash: str | None
  hash: str
```

**[TODAY]**: `governance/evidence.py`'s `EvidenceRecord` +
`db/evidence_repository.py`'s `EvidenceRepository` implement a real,
persisted, hash-chained subset of the shape above —
`tests/test_governance_persistence.py` proves tamper detection
(mutating a stored field, or breaking the `prev_hash` link between two
entries, both make `verify_chain()` return `False`) and per-org chain
independence. This generalizes the AI Incident Database's proven
hash-chaining pattern (`db/public_incident_repository.py`,
`GET /api/incident-db/verify`) into per-org evidence rather than
inventing tamper-evidence from scratch, exactly as originally planned
— except chained **per organization**, not globally, since an org's own
evidence trail should be independently verifiable without needing any
other org's records. Exposed via `GET /api/governance/evidence` and
`GET /api/governance/evidence/verify`.

Field-by-field honesty against the target shape above —
`governance/evidence.py`'s module docstring has the full accounting,
summarized: `sanitized_arguments_metadata` is implemented as
`argument_keys: list[str]` (field *names* only, deliberately never
values); `trust_signals` is not populated (nothing computes a live
`TrustCheckResult` automatically yet); `deterministic_checks` /
`probabilistic_checks` are not broken out as separate structured
fields, `reason_codes` carries what a `GuardrailsResult`/`Policy` match
found instead; `execution_result_metadata` is not populated (this
package has no visibility into whether an allowed action was actually
executed); `human_identity` is populated from
`AgentContext.identity.identity_id`, since no concept of "the human
behind the agent, distinct from the API key/OIDC identity that
authorized it" exists yet.

---

## 4. The WhitePact Governance Engine — mapping today's 27 MCP tools

**[TODAY, verified against `src/responsibleai/mcp/tools.py`]**: exactly
27 tools are registered via `TOOL_DEFS`, dispatched through
`dispatch_tool()`. Under the target architecture, these become the
**deep governance intelligence** the Decision pipeline calls into —
they do not disappear, get renamed at the tool level, or lose their
existing MCP-client-facing contract. They are reorganized conceptually
into the risk-tiered execution model (Phase 9):

| Tier | Risk | Existing tools (verified names) |
|---|---|---|
| Identity/health (near-zero cost, safe to run on every request) | MINIMAL | `rai_health`, `rai_audit_summary`, `rai_org_status` |
| Deterministic scan (fast, no LLM) | LOW | `rai_scan` (PII/harm detection), `rai_pii_report`, `rai_policy_check`, `rai_stream_scan` |
| Trust/cost lookups (cached-friendly) | LOW | `rai_trust_score`, `rai_check_trust`, `rai_cost_estimate`, `rai_budget_check`, `rai_model_route` |
| Compliance classification | MEDIUM | `rai_compliance`, `rai_eu_ai_act_classify`, `rai_iso42001_gap` |
| Deeper/probabilistic evaluation | HIGH | `rai_hallucination`, `rai_bias_evaluate`, `rai_drift_check`, `rai_redteam_payloads`, `rai_redteam_analyze`, `rai_compare_models`, `rai_benchmark`, `rai_benchmark_prompts` |
| Record-keeping (writes — never mislabel as read-only) | MEDIUM | `rai_incident_log`, `rai_passport_generate`, `rai_executive_summary`, `rai_webhook_status` |

**[TODAY]**: this table is now executable, not just proposed —
`governance/risk.py`'s `TOOL_RISK_TIERS` and `classify_action_risk()`
implement it exactly (`tests/test_governance_risk.py` asserts the table
stays in sync with the live `TOOL_DEFS` list, so it can't silently drift
as tools are added). What "risk-tiered execution" doesn't yet mean:
there's no automatic behavioral difference *between* the four tiers
baked into the gateway itself — a `HIGH`-tier action isn't automatically
held for approval or subjected to extra scrutiny by `risk.py` alone. The
tier is a real, computed classification made available to a `Policy`
(Section 3.5) to act on; whether it actually changes a decision depends
entirely on whether an organization's `Policy` has a rule that reads it.
No default policy ships that does this automatically — that would be an
opinionated governance stance imposed on every deployment, not a neutral
capability.

### 4.1 MCP Trust/Supply-Chain Scanner **[TODAY, first version — Phase 13]**

Before this section's work: no code anywhere evaluated the
trustworthiness of a *third-party* MCP server before an organization
grants an agent authority to use it — a real gap distinct from
everything else in this document, which governs actions against
*this* server's own tools, not decides whether to trust *someone
else's*.

**[TODAY]**: `src/responsibleai/supplychain/` — `SupplyChainScanner`
takes a caller-supplied `McpServerManifest` (server name, publisher,
tool name/description list) and returns a `SupplyChainReport`: a list
of `Finding`s, each classified `VERIFIED_FACT` / `INFERRED_SIGNAL` /
`UNKNOWN` — never collapsed into a single opaque score, per this
section's one hard requirement. Three checks, each honestly scoped to
what it can actually claim:

1. **Confusable-character check** (`VERIFIED_FACT` either way) — a
   bounded Cyrillic/Greek lookalike-character lookup table against
   server and tool names (the classic typosquat trick). Presence or
   absence is a verifiable fact about the string itself. Deliberately
   *not* a full Unicode TR39 confusables implementation — that's real,
   separate, larger work; this is a stated, bounded subset.
2. **Tool description content scan** (always `INFERRED_SIGNAL`) —
   reuses the existing, tested `GuardrailsEngine` against every tool
   description, looking for injected-instruction/PII/toxicity patterns.
   A match is a signal worth a human look; a clean scan is not proof of
   safety, only that this heuristic found nothing.
3. **Known public incident cross-reference** (`VERIFIED_FACT` if found,
   `UNKNOWN` if not — optional, needs a `PublicIncidentRepository`) —
   reuses the existing AI Incident Database's `check()` method. Filed
   incidents are a real fact; their absence is explicitly *not* treated
   as evidence of safety, since a new or low-visibility server may
   simply not have been scrutinized yet.

This scanner never connects to a remote MCP server itself — it
analyzes whatever manifest a caller already has (from a real
`tools/list` response, a registry listing, etc.). Actually speaking
the MCP protocol to an arbitrary third-party server is real, separate
transport-layer work with its own security questions (SSRF risk in
fetching an arbitrary server-supplied URL, for one), not implied by
this scanner's existence. Exposed via `POST
/api/governance/supplychain/scan` (not org-scoped: the checks are
either pure or query the public, org-agnostic incident database, so
there's no per-org data to isolate).

---

## 5. Multi-tenancy and organization boundary **[TODAY]**

Every entity in this spec that carries `organization_id` is not
aspirational — real multi-tenant isolation exists today: `OrgContext`,
per-org rate limiting (SHA-256-keyed bearer tokens, not a shared global
pool), and RBAC roles scoped per organization. The target architecture's
`AgentContext.organization_id` and `EvidenceRecord.organization_id` are
designed to compose with this existing boundary, not replace it.

---

## 6. Deterministic vs. probabilistic controls

This distinction is a first-class architectural principle, not an
afterthought (see `MIGRATION_WHITEPACT_V2.md` Phase 24 for the dedicated
document this spec's principle will expand into).

**Deterministic** (same input → same output, always, no model call):
identity checks, RBAC role checks, rate limits, `rai_scan`'s
regex/pattern-based PII detection, policy threshold rules, cryptographic
hash-chain verification.

**Probabilistic** (a model or heuristic produces a confidence-scored
judgment): `rai_hallucination`'s risk scoring, `rai_bias_evaluate`'s
probe-based bias detection, semantic policy interpretation (not yet
built).

**Rule**: WhitePact must never present a probabilistic evaluation's
output as a guarantee. Every probabilistic result in `EvidenceRecord`
must carry a confidence/limitation annotation, and the fast, low-risk
decision path (Phase 9's LOW tier) must be satisfiable using
*deterministic* checks alone — an agent should never be forced through
an LLM call just to get a routine, low-risk action approved.

---

## 7. What this spec deliberately does not yet define

Per this project's own engineering discipline (no speculative
architecture beyond what's needed): the following are named in the
migration plan but intentionally left undesigned in this document until
their own phase is reached, so this spec doesn't accumulate unreviewed
speculative detail:

- A richer policy rule language beyond `PolicyRule`'s plain
  risk-tier/action-type/target matching (Phase 10's first version now
  exists — see Section 3.5 — but OPA/Rego or an expression language, if
  ever needed, is still undesigned).
- A richer approval-workflow lifecycle beyond `ApprovalRequest`'s
  `PENDING -> APPROVED`/`DENIED` (Phase 11's first version now exists —
  see Section 3.6's `REQUIRE_APPROVAL` row — but expiry/timeout,
  multi-approver quorum, and delegation-chain approval are still
  undesigned).
- A richer MCP Trust/Supply-Chain Scanner than the three checks in
  Section 4.1 (Phase 13's first version now exists — confusable
  characters, tool description content scan, known-incident
  cross-reference — but a full Unicode TR39 confusables implementation,
  publisher/domain identity verification, and actually connecting to a
  remote MCP server to fetch its manifest are all still undesigned).
- OAuth/OIDC scope names for remote MCP authorization (Phase 6) — to be
  designed against the actual current MCP specification, not guessed
  here.

---

## 8. Relationship to existing product documents

- `GAME_CHANGER_STRATEGY.md` / `GAME_CHANGER_BUILD_PLAN.md` — the
  infrastructure-first distribution bet (free public trust registry,
  agent-framework trust-check integrations). Still valid; WhitePact's
  runtime gateway is a superset, not a replacement, of that plan's
  `rai_check_trust` primitive.
- `VERSION_ROADMAP.md` / `STRATEGY_ROADMAP.md` — the pre-WhitePact
  version-numbered and business-phase roadmaps. Superseded in spirit by
  `MIGRATION_WHITEPACT_V2.md` for anything touching product identity;
  still accurate for governance-engine feature history.
- `TRUST_INDEX_SPEC.md`, `LEADERBOARD_METHODOLOGY.md` — unchanged,
  still the authoritative spec for those specific subsystems, which this
  document's Governance Engine section references rather than
  duplicates.

---

## 9. Package identity note

This spec is written using `WhitePact`-facing conceptual names
(`AgentContext`, `GovernanceDecision`, etc.) for the target architecture.
The actual Python package remains `src/responsibleai/` at the time of
this writing (158 files reference the `responsibleai` import path; see
the baseline audit). Phase 8's runtime governance core will land as new
modules; whether they live under a new `src/whitepact/` package or
inside the existing tree during a staged migration is decided in
`MIGRATION_WHITEPACT_V2.md`, not in this spec — this document defines
*what* the architecture is, not the filesystem layout of the migration.
