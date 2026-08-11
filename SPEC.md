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

Last reviewed: 2026-07-26 · Repository: `Guruprasath-Annadurai/Whitepact`
(renamed from `ResponsibleAi`; package identity migration in progress —
see Section 9).

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

## 2. The core pipeline **[TARGET]**

```
Organization
  → delegates authority to
Agent (identity + framework + model)
  → proposes
Action (an MCP tool call, an API operation, a transaction, a data export...)
  → evaluated against
Policy (deterministic organizational rules)
  → informed by
Trust (existing Trust Index / leaderboard signals)
  → and
Risk (classified severity of the action)
  → produces a
Decision: ALLOW | ALLOW_WITH_REDACTION | REQUIRE_APPROVAL | DENY | QUARANTINE
  → routes to
Execution (the actual MCP/API/SaaS/database call, only if allowed)
  → and always produces
Evidence (an immutable, exportable record of the whole decision)
```

Nothing in this pipeline exists as a wired-together runtime today.
**[TODAY]**, the pieces exist as independent, callable components (an
MCP tool computes a trust score; a guardrails engine returns
`is_blocked: bool`; RBAC gates who can call which REST endpoint) but
there is no single component that takes "agent proposes action" as
input and returns one of the five decisions above as output. Building
that component — the **WhitePact Runtime Gateway** — is what Phase 8
(`RUNTIME GOVERNANCE CORE`) of the migration plan does.

---

## 3. Core entities

### 3.1 Agent **[TARGET — new model]**

An autonomous or semi-autonomous software actor requesting an action.

```
AgentContext:
  agent_id: str                 # stable identifier for this agent instance
  organization_id: str          # tenant boundary — see RBAC below
  identity: IdentityContext     # who/what is actually behind this agent
  framework: str | None         # e.g. "langchain", "langgraph", "adk", "mcp-client"
  provider: str | None          # e.g. "openai", "anthropic", "azure-openai"
  model: str | None             # e.g. "gpt-4o", a customer's Azure deployment name
  trust_state: TrustSummary | None  # cached Trust Index result for this agent/tool, if known
  metadata: dict[str, Any]      # framework-specific extras, never secrets
```

**[TODAY]**: the closest existing concept is `TrustCheckResult`
(`src/responsibleai/integrations/client.py`) — a lookup of a *model or
tool's* public trust score, not a structured record of an *agent
instance* making a request. `AgentContext` as defined above does not
exist yet.

### 3.2 Identity **[TARGET, partially TODAY]**

Who or what is making the request. Must support humans, service
accounts, agents, API keys, OAuth/OIDC identities, and future workload
identities.

**[TODAY]**: `OrgContext` (`src/responsibleai/rbac/models.py`) already
carries `key_id`, `role` (`OWNER`/`ADMIN`/`ANALYST`/`VIEWER`), `org_id`,
and `plan` — this is a real, working, tested identity model, but it's
scoped to *human/API-key* access to the REST API and dashboard, not to
an *agent* acting on a human's or organization's behalf. OIDC/SSO
support exists (`src/responsibleai/auth/` — see `sso` extra in
`pyproject.toml`). MFA (TOTP, RFC 6238) is implemented and tested. None
of this is currently extended to represent "this specific agent
instance, running under this delegated authority, on behalf of this
organization."

`IdentityContext` in the target architecture generalizes `OrgContext` to
cover agent identities and future workload identities (e.g. SPIFFE/SPIRE
-style), without breaking the existing human/API-key identity model.

### 3.3 Authority **[TARGET — new concept]**

What authority has been delegated to the agent. This is deliberately
**not** the same thing as a raw RBAC role.

- **RBAC/IAM question**: does this API key have the `ADMIN` role, which
  technically permits calling `POST /api/trust-index/certify`?
- **Authority question**: even though this agent's identity *can*
  technically reach that endpoint, has this organization actually
  delegated "certify trust passports" authority to *this specific
  agent*, in *this context* (time of day, transaction value, data
  sensitivity, environment)?

**[TODAY]**: no `AuthorityContext` or delegation model exists. RBAC
roles are the only authority signal in the codebase today, and they are
static and human-provisioned, not scoped per-agent or per-action-context.
This is new architecture, built in Phase 8.

### 3.4 Action **[TARGET — new model]**

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

**[TODAY]**: the closest analogue is an MCP tool call itself
(`dispatch_tool(name, args)` in `src/responsibleai/mcp/tools.py`) — real,
tested, 27 tools registered — but there is no generic `ActionRequest`
abstraction that covers non-MCP actions (a database write, a payment, an
approval) the way this target model does.

### 3.5 Policy **[TARGET — new subsystem]**

Machine-enforceable organizational rules governing actions. See Phase 10
of the migration plan for the policy engine design (a small, strongly
typed internal model first — not an LLM, not necessarily OPA/Rego on day
one; see Section 6 below on deterministic vs. probabilistic controls).

**[TODAY]**: `rai_policy_check` (an existing MCP tool) evaluates text or
a response against a governance policy template (blocklists,
disclaimers) — a real, narrow, working feature. It is not the
general-purpose, reason-coded, threshold-aware policy engine described
in Phase 10. There is no `src/responsibleai/policy/` package today (a
directory search confirms this).

### 3.6 Decision **[TARGET — new model]**

One of exactly five outcomes:

| Decision | Meaning |
|---|---|
| `ALLOW` | The action proceeds unmodified. |
| `ALLOW_WITH_REDACTION` | The action proceeds, but the payload is modified first (e.g. PII stripped) — see `GuardrailsEngine`'s existing redaction logic, which this reuses. |
| `REQUIRE_APPROVAL` | The action is held pending a human (or delegated-authority) approval — see Section 3.7 and the forthcoming approval-workflow phase. |
| `DENY` | The action is blocked outright. |
| `QUARANTINE` | The action, the agent, or both are held for review beyond a single decision — e.g. an agent exhibiting a pattern of policy violations gets its authority suspended pending investigation, distinct from a single denied action. |

**[TODAY]**: every existing decision-shaped output in this codebase is
binary. `GuardrailsEngine.scan()` returns `is_blocked: bool`
(`src/responsibleai/guardrails/engine.py`). There is no five-way
`GovernanceDecision` enum anywhere in source today. This is the single
most consequential net-new piece of Phase 8.

### 3.7 Evidence **[TARGET — new model]**

Immutable, tamper-evident structured evidence for every decision.
Conceptually:

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

**[TODAY]**: this project already has a real, tested, hash-chained
audit/evidence primitive — the AI Incident Database
(`src/responsibleai/db/public_incident_repository.py`) uses hash
chaining with a verifiable `GET /api/incident-db/verify` endpoint, and
the standard audit log (`AuditRepository`) records every HTTP request.
Neither is shaped as a per-*governance-decision* evidence record the way
`EvidenceRecord` is designed to be — Phase 12 generalizes the existing
hash-chaining pattern (already proven correct and tested) into
`EvidenceRecord`, rather than inventing tamper-evidence from scratch.

---

## 4. The WhitePact Governance Engine — mapping today's 27 MCP tools

**[TODAY, verified against `src/responsibleai/mcp/tools.py`]**: exactly
27 tools are registered via `TOOL_DEFS`, dispatched through
`dispatch_tool()`. Under the target architecture, these become the
**deep governance intelligence** the Decision pipeline calls into —
they do not disappear, get renamed at the tool level, or lose their
existing MCP-client-facing contract. They are reorganized conceptually
into the risk-tiered execution model (Phase 9):

| Tier | Existing tools (verified names) |
|---|---|
| Identity/health (near-zero cost, safe to run on every request) | `rai_health`, `rai_audit_summary`, `rai_org_status` |
| Deterministic scan (fast, no LLM) | `rai_scan` (PII/harm detection), `rai_pii_report`, `rai_policy_check`, `rai_stream_scan` |
| Trust/cost lookups (cached-friendly) | `rai_trust_score`, `rai_check_trust`, `rai_cost_estimate`, `rai_budget_check`, `rai_model_route` |
| Compliance classification | `rai_compliance`, `rai_eu_ai_act_classify`, `rai_iso42001_gap` |
| Deeper/probabilistic evaluation (reserved for HIGH/CRITICAL risk actions) | `rai_hallucination`, `rai_bias_evaluate`, `rai_drift_check`, `rai_redteam_payloads`, `rai_redteam_analyze`, `rai_compare_models`, `rai_benchmark`, `rai_benchmark_prompts` |
| Record-keeping (writes — never mislabel as read-only) | `rai_incident_log`, `rai_passport_generate`, `rai_executive_summary`, `rai_webhook_status` |

This table is a **proposed** tiering for Phase 9's risk router — it has
not been implemented as executable routing logic yet. It's recorded here
so the tiering decision is made once, deliberately, and reviewably,
rather than invented ad hoc when Phase 9 starts.

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

- The exact policy rule language/schema (Phase 10).
- The approval-workflow state machine's persistence schema (Phase 11).
- The MCP Trust/Supply-Chain Scanner's scoring methodology (Phase 13) —
  this explicitly must distinguish VERIFIED FACT / INFERRED SIGNAL /
  UNKNOWN per input, not produce a single opaque score.
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
