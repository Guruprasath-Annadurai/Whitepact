# Enforcement Boundary

Last reviewed: 2026-08-17 · Platform version: 1.2.0

`MACHINE_AUTHORITY_V1.md` inventories what's built. This document states,
as precisely as possible, **where each primitive's authority actually
stops** — the difference between "WhitePact can deny this" and "WhitePact
never sees this at all." Getting this wrong in either direction is a real
risk: understating the boundary looks like false modesty; overstating it
is the kind of claim that gets a real incident blamed on a control that
was never actually in the path. Read this alongside `THREAT_MODEL.md`
(the STRIDE-structured surface analysis) — that document covers the attack
surface of WhitePact itself; this one covers the surface WhitePact's
governance decisions actually reach.

## The core distinction: inline enforcement vs. a voluntary chokepoint

Two of WhitePact's enforcement points are **inline** — a call cannot reach
its destination without physically passing through WhitePact's code first:

- **The hosted MCP dispatch path**, when `Settings.mcp_governance_enabled`
  is `True` (default `False`). `_call_tool()` in `mcp/server.py` calls
  `apply_governance()` before `dispatch_tool()`; the only path to a tool
  actually running is through `authorize_execution()` and
  `InternalToolExecutor` — there is no code path where a governed call
  reaches `dispatch_tool()` without first passing evaluation.
- **The MCP Upstream Gateway proxy** (`governance/upstream_executor.py`) —
  for an upstream MCP server an org has explicitly registered, calls are
  proxied through WhitePact's own SSRF-guarded executor, not sent directly
  from the caller to the upstream server.

Everything else described in `MACHINE_AUTHORITY_V1.md` is a **voluntary
chokepoint**: a library or endpoint that produces a correct decision *if
and only if the caller's own code chooses to call it first*. This is not a
weakness unique to WhitePact — it's the honest shape of the two problems
those primitives solve:

- **Memory Authority** (`rai_memory_write_check`/`rai_memory_read_check`,
  `memory_scope`): WhitePact hosts no memory store. It cannot intercept a
  write to a company's own vector DB or conversation log the way a
  database proxy could — the company's own memory-writing code has to call
  `rai_memory_write_check` before persisting, exactly the way it would call
  any other validation step. If it doesn't, the write happens ungoverned.
- **A2A Trust Gate** (`integrations/a2a_adapter.py`): WhitePact is not an
  A2A relay or service mesh. `A2ATrustGate.check()` produces a real
  allow/block decision, but only for the caller who invokes it before
  sending — there is no network-level interception of A2A traffic.
- **The REST governance API** (`/api/governance/*`, ceiling/budget/rule
  configuration endpoints): these persist configuration and answer
  queries; they do not themselves intercept any traffic. Their effect is
  real only through the inline dispatch path reading that configuration
  on every call.

If a deployment's threat model requires inline enforcement for memory or
A2A traffic specifically, that's real, separate infrastructure work (a
memory-store proxy, an A2A relay) that does not exist in this codebase —
stated here explicitly rather than implied by proximity to the tools that
do exist.

## What the inline hosted-dispatch path does NOT cover

Even where enforcement is inline, it is not universal:

- **The self-hosted stdio transport is never governed, regardless of the
  `mcp_governance_enabled` setting.** `apply_governance()` requires an
  org-scoped `OrgContext` (`ctx.org_id is not None`) to build an
  `AuthorityContext`/`Policy` against; a local stdio process invoked
  directly (`responsibleai-mcp` / `whitepact-mcp`) has no such organizational
  identity and is architecturally out of reach of this governance layer.
  This is not a bug to fix — a local process with no org context has
  nothing for `AuthorityContext` to be scoped to — but it means "I run
  WhitePact's MCP server" and "my calls are governed" are not the same
  claim unless the caller is specifically using the hosted HTTP transport
  with the flag on.
- **A legacy flat (non-org-scoped) API key skips governance entirely** —
  `_call_tool()` checks for an org-scoped `ctx` and falls through to
  ungoverned `dispatch_tool()` for a flat key, by design (a flat key has
  no org to build `AuthorityContext`/`Policy` against either).
- **Anything a caller's own code does *after* a governed tool call
  completes is outside the governed action itself.** WhitePact governs the
  decision to run a specific, named action with specific arguments — it
  has no visibility into what an LLM or agent framework does with that
  action's *result* afterward (a classic "confused deputy" risk any
  policy-engine-at-the-tool-call-layer design shares, not specific to this
  codebase).
- **`execution_result_metadata` is not populated** (see
  `governance/evidence.py`'s own honest-scoping note) — WhitePact records
  the decision to allow/deny/redact an action, not proof of what the
  action's execution actually did downstream.

## What every primitive's scope actually is, one line each

- **Authority Attenuation / Delegation Graph**: governs grants made
  *through this graph* (`DelegationRepository.grant()`). An org that
  manages authority some other way (its own IAM, a different delegation
  mechanism) gets no attenuation checking from WhitePact for those grants.
- **Org Authority Ceiling**: governs calls that reach the gateway with a
  `ctx.org_id` matching a configured ceiling. No ceiling row means no
  ceiling — the honest default, not a hidden restriction.
- **Workflow Authority Engine**: governs sequences *within one agent's own
  evidence history* in one org (`EvidenceRepository.list_recent_actions()`,
  scoped by `agent_id` and `org_id`). A sequence split across two different
  API keys/agents acting in coordination is not currently detected — each
  identity's history is evaluated independently.
- **Continuous MCP Trust**: caching is opt-in per `TrustClient` instance;
  only the governed hosted-dispatch path's client opts in. A caller using
  `TrustClient()` directly (LangChain/LangGraph/ADK integrations,
  `rai_check_trust`) gets the pre-existing always-live-fetch behavior,
  unaffected.
- **Autonomy Budget**: counts `ALLOW`/`ALLOW_WITH_REDACTION` decisions
  recorded through this gateway, per `(org_id, agent_id)`. An agent that
  fans work out across multiple API keys/agent identities is not currently
  aggregated into one shared budget.
- **Evidence Bundle**: exports and verifies exactly the `governance_evidence`
  rows this gateway wrote. It is not an audit trail for actions taken
  outside this governance layer.

## Revisiting this document

Update this document the same day a new inline enforcement point ships, or
whenever an existing voluntary chokepoint gains real inline interception —
the boundary described here is a factual claim about the current code, not
a roadmap. A stale enforcement-boundary doc that implies coverage that
doesn't exist is worse than an honestly narrow one; see `SECURITY.md` for
how to report a discrepancy.
