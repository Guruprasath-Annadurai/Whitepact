# Phase 10 — Brain Policy + Risk Engine: Design

## Objective

Per the master directive's Phase 10 ("Brain Policy + Risk Engine"):
verify the runtime policy/risk pipeline — SPEC.md's "the Brain" —
against the real, existing codebase. Per directive rule 63 ("inspect
before implementing... do not rebuild systems merely to satisfy this
prompt"), and per Phase 8's own closing note ("Phase 10 likely
warrants the same audit-first approach before assuming net-new
scope"): audit first, implement only genuine gaps.

## Audit: what already exists

SPEC.md §2.5 names the "Brain" explicitly: "the existing
gateway/policy/risk pipeline" — and states the canonical relationship
`EXECUTABLE_AUTHORITY ⊆ BRAIN_AUTHORITY ⊆ HEART_AUTHORITY`. This is
not a new component to build; it is the pre-existing risk/policy
pipeline this directive's own Phase 10 name refers to.

Confirmed by reading `governance/gateway.py`'s own docstring (lines
41-55): step 3 of `WhitePactRuntimeGateway.evaluate()` is literally
labeled "Risk classification (Phase 9, `governance/risk.py`)" and step
4 is literally labeled "Policy (Phase 10, `governance/policy.py`,
optional)" — using SPEC.md's own pre-existing phase numbering, which
this directive's Phase 10 name evidently refers back to.

**Real, tested, already in production:**

- `governance/risk.py` — `RiskTier` (MINIMAL/LOW/MEDIUM/HIGH),
  `TOOL_RISK_TIERS` (all 27 first-party tools classified, SPEC.md
  §4's tiering table made executable), `classify_action_risk()`.
  Honest MEDIUM default for unrecognized action types (not MINIMAL —
  unclassified is not the same claim as verified-safe). Upstream MCP
  proxy calls default to HIGH, not the unrecognized-action MEDIUM,
  since a third-party server is inherently less verified than this
  platform's own tools.
- `governance/policy.py` — `PolicyRule` (deterministic
  risk-tier/action-type/target matching, no expression language),
  `Policy` (ordered, first-match-wins rule set, versioned).
  Deliberately excludes `ALLOW_WITH_REDACTION` (guardrails' job) and
  `QUARANTINE` (needs cross-request state a rule never sees).
- `db/policy_repository.py` — `PolicyRepository`: per-org persisted,
  versioned rule sets (`add_rule`, `remove_rule`, `reorder`,
  `get_policy`), backed by `governance_policies` /
  `governance_policy_versions` tables.
- Wired into **both** live governed-call paths, unconditionally (not
  optionally skipped):
  - `mcp/governance_integration.py:258` — `policy =
    await services.policy_repo.get_policy(ctx.org_id)`, then passed
    to `gateway.evaluate()` on every hosted MCP tool call.
  - `mcp/upstream_dispatch.py:200-204` — same pattern for calls
    proxied to third-party upstream MCP servers.
- Extensively tested: `tests/test_governance_risk.py` (11),
  `tests/test_governance_policy.py` (12),
  `tests/test_policy_repository.py` (18), plus dozens of indirect
  exercises across `test_governance_core.py`, `test_concurrency.py`,
  `test_approval_*.py`, `test_governance_quarantine.py`,
  `test_workflow_authority.py`, `test_upstream_gateway.py`.

**Verified via source-text scan** (same heuristic as Phase 8's
guards): `policy.evaluate(action, risk_tier)` at `gateway.py:269` is
the **only** call site of `Policy.evaluate()` anywhere in
`src/responsibleai/**/*.py`. `classify_action_risk()` has exactly
three call sites: `gateway.py:183` (the gated evaluation itself) and
two in `upstream_dispatch.py` (144, 183) — both pre-gateway
short-circuit DENY paths (unregistered server, BLOCKED trust tier)
that still need a `risk_tier` value for evidence/observability
consistency on an early exit, not a second policy-evaluation path.

## What SPEC.md itself names as still-[TARGET] — deliberately not this phase

- **A richer policy rule language (OPA/Rego)** beyond the current flat
  first-match-wins matching. SPEC.md §3.5 explicitly states this is
  "explicitly left for a later iteration, not implied by this one."
  Rebuilding the rule engine now would be exactly the unrequested
  rebuild directive rule 63 prohibits.
- **Governing the self-hosted stdio transport.** Already named as a
  real, out-of-scope gap in Phase 8 (`08_PHASE8_REPORT.md`, Gap 1) —
  it has no organizational identity to build a `Policy`/risk-tier
  decision against in the first place, so this is architectural, not
  an oversight this phase could close.

## Conclusion: audit-driven, like Phase 8

The Brain (risk classification + policy engine) is real, persisted,
tested, and unconditionally wired into every live governed-call path.
No rebuild is warranted. This phase's genuine, narrowly-scoped
contribution is the same kind Phase 8 delivered: **regression-tested
evidence** that the properties above hold, so a future change that
silently breaks them (a second `Policy.evaluate()` call site bypassing
`gateway.py`'s ordering, or a call path that never loads
`PolicyRepository` at all) is caught by CI, not discovered later.

## Scope for this phase

New file: `tests/test_brain_policy_risk_boundary.py`:

1. Structural guard: `Policy.evaluate()` has exactly one call site
   (`gateway.py`).
2. Structural guard: `classify_action_risk()` has exactly the three
   known call sites (gateway.py + the two documented pre-gateway
   short-circuits in upstream_dispatch.py) — a new, unaccounted-for
   call site would mean risk tiering happening somewhere the audit
   above doesn't know about.
3. Runtime: every `DecisionResult` produced by
   `WhitePactRuntimeGateway.evaluate()` has a non-`None` `risk_tier`
   — "every action gets a RiskTier" (gateway.py's own docstring,
   step 3) as an enforced property, not just a comment.
4. Runtime adversarial: a `Policy` rule set with a `DENY` rule
   matching a given risk tier/action type actually produces `DENY`
   through the real `WhitePactRuntimeGateway.evaluate()` — and an
   attacker-controlled `ActionRequest.arguments` payload shaped to
   look like an override (`{"risk_tier": "MINIMAL", "policy_effect":
   "ALLOW"}`) has no effect on the outcome, since risk tier is
   computed from `action_type`/`target` only and policy effect comes
   from the org's persisted `Policy`, never from request arguments.
5. Runtime: `classify_action_risk` returns the documented honest
   defaults — MEDIUM for an unrecognized action type, HIGH for the
   upstream-proxy action type — verified against the real function,
   not restated as an assumption.

No source file changes. No new architecture. No database migration.
