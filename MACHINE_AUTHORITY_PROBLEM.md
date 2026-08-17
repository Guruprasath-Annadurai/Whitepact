# The Machine Authority Problem

Last reviewed: 2026-08-17 · Platform version: 1.2.0

This document states, plainly, the problem WhitePact's v3 authority-layer
work (`MACHINE_AUTHORITY_V1.md`) was built to answer. It does not claim
WhitePact solves all of it — see `ENFORCEMENT_BOUNDARY.md` for what's
actually enforced today, and each linked module's own docstring for what
remains honestly out of scope.

## The problem is not "authorization." It's authorization at agent speed,
## with agents delegating to agents.

Traditional access control — RBAC, OAuth scopes, IAM policy documents —
answers one question: *can this identity call this endpoint?* That question
was designed around a human (or a service acting on a human's behalf)
making a bounded number of calls, at human-reviewable frequency, where the
identity calling the endpoint is the identity that decided to call it.

Autonomous and semi-autonomous AI agents break every one of those
assumptions at once:

1. **Delegated authority compounds, and can silently escalate.** A human
   grants an agent authority to do X. The agent may itself spawn or
   instruct a sub-agent, delegating a slice of that authority onward. Each
   hop is a place authority can be — accidentally or adversarially —
   widened rather than narrowed, and nothing in a traditional RBAC role
   check notices, because RBAC roles aren't built to compare a delegated
   grant against what its delegator actually held.
2. **Volume replaces review.** A human approval step assumes a human is in
   the loop often enough to catch a problem. An agent that's correctly
   authorized for every individual action can still execute thousands of
   those actions with no human ever looking — the danger isn't any single
   call, it's that nobody is checking in.
3. **Agents call other agents, not just tools.** MCP governs "agent calls a
   function." A growing share of real agent architectures also have "agent
   sends a task to another agent it doesn't control" (A2A and similar
   protocols) — a trust boundary with no equivalent in a service mesh's
   mTLS model, because the question isn't "is this the service it claims to
   be," it's "should I act on what this *other agent* is telling me to do."
4. **Persistent memory is a second attack surface for the same content.** A
   toxic or manipulative string in a normal tool-call argument is seen once
   by one call. The same content, written into memory an agent reads back
   in a future session, becomes part of what the agent treats as its own
   trusted prior reasoning — an injection that fails against the current
   turn can still succeed weeks later.
5. **A model or an upstream agent's trustworthiness isn't a fact you check
   once.** A vendor's model can be re-trained, a certification can lapse, a
   partner agent can be compromised after the first call that trusted it.
   Caching "we checked this yesterday" forever is exactly as wrong as never
   caching it — both extremes either grind every call to a network
   round-trip or let a stale trust judgment quietly go unrevisited.
6. **The evidence has to survive the system that produced it.** An
   incident, audit, or insurance claim happens after the fact, often by a
   party (a regulator, an auditor, an underwriter) who has no ongoing
   access to the live system and no reason to trust its live "yes, that's
   accurate" — they need something they can verify standing entirely on
   their own.

None of these six are solved by "add more RBAC roles" or "add another OAuth
scope." They're a different shape of problem: not *who may call this*, but
*how far can delegated, unsupervised, cross-agent authority actually run
before something requires a human to look, and can I prove after the fact
exactly what ran and why.*

## What "machine authority" means in this codebase

Concretely, and only these things — not a marketing term for "AI safety" in
general:

- **Authority that narrows, never widens, across a delegation chain**
  (`governance/models.py`'s `validate_attenuation()` — Core Invariant #1).
- **A real, persisted, queryable graph of who delegated to whom**, not just
  an in-memory list carried on one call (`governance/delegation.py`,
  `db/delegation_repository.py` — Core Invariant #2), with cascading
  revocation and continuous re-authorization (a delegation checked valid
  once is re-checked, not trusted forever, on every subsequent call).
- **Detection of a dangerous combination of individually-permitted
  actions** (`governance/workflow.py`'s `check_composition_violation()` —
  Core Invariant #3), since attenuation alone can't catch a sequence that's
  only dangerous in combination.
- **A structural ceiling no per-call authority can exceed**
  (`governance/ceiling.py`), a **volume cap on unsupervised execution**
  independent of whether any individual call was risky
  (`governance/autonomy_budget.py`), and a **gate on the trustworthiness of
  another agent before sending it a task**
  (`integrations/a2a_adapter.py`'s `A2ATrustGate`).
- **A dedicated scan for content trying to poison persistent memory**
  (`governance/memory_firewall.py`), distinct from and complementary to the
  general PII/toxicity scan every action's arguments already go through.
- **Trust checks with bounded staleness, not "check once, cache forever"**
  (`integrations/client.py`'s `TrustClient` caching + `TrustCheckResult.stale`).
- **An offline-verifiable, tamper-evident export of everything decided**
  (`governance/evidence_bundle.py`), so the proof survives independent of
  continued access to the system that produced it.

Each of these is documented, tested, and load-bearing today — see
`MACHINE_AUTHORITY_V1.md` for the full inventory and `ENFORCEMENT_BOUNDARY.md`
for exactly where each one's authority stops.
