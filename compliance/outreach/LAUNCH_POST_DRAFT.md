# Launch post drafts

> Drafted for `FOUNDER_ACTION_CHECKLIST.md` Section 1's "Write a short
> launch post (blog, LinkedIn, 'Show HN' if applicable)." Every claim
> below was checked live on 2026-08-14 before writing this — dashboard,
> `/registry`, `/assess` all returned HTTP 200, the PyPI package
> responds, the MCP Registry listing is live. Nothing here is
> aspirational copy; if a fact changes before you post, update this
> draft rather than posting stale numbers.
>
> You only need to review and post — no further drafting required. Pick
> the platform(s) that fit; both variants below say the same true
> things, framed for the audience reading them.

---

## Show HN (news.ycombinator.com)

**Title** (HN convention: "Show HN: X – one factual line, no
superlatives", under ~80 chars):

> Show HN: WhitePact – open governance layer for AI agents, 27 MCP tools

**Body**:

I built WhitePact because every AI-agent project I looked at had the
same gap: no unified way to check whether a specific AI system or
agent action is safe, fair, compliant, or accountable — you either get
informal marketing claims ("our AI is safe") or a formal regulatory
framework (EU AI Act, NIST AI RMF) that's comprehensive but not a
single number you can act on in code.

WhitePact is a governance/trust layer that sits in front of an agent's
tool calls, not another model. It's a Python package, a REST API, and
an MCP server (27 tools, works over stdio, Streamable HTTP, or legacy
SSE) that gives you:

- A deterministic 5-way decision (ALLOW / ALLOW_WITH_REDACTION /
  REQUIRE_APPROVAL / DENY / QUARANTINE) for a proposed agent action —
  no LLM call in the decision path itself, so it's not "ask another AI
  if this AI is trustworthy."
- A 6-dimension Trust Score (fairness, privacy, security, robustness,
  compliance, authenticity), open-specified, not a black box — the
  weights and grade bands are in the repo, same numbers the code
  actually runs.
- PII/harmful-content guardrails, hallucination detection, red-team
  probes (10 attack vectors), and compliance mapping against NIST AI
  RMF / EU AI Act / ISO 42001.
- A public, free self-assessment + verification endpoint
  (`/api/trust-index/verify/{id}`) so a cited trust score is something
  anyone can actually check, not an unfalsifiable claim — and a
  cross-model leaderboard computed by actually calling each model's
  API, not self-reported numbers.

What it's genuinely not: a certification. Self-assessed scores are
labeled `certified: false` everywhere they're shown — I built the
provenance labeling specifically so a self-reported number can never
look identical to a human-reviewed one.

Try it with zero signup: [https://responsibleai-dashboard.onrender.com/registry](https://responsibleai-dashboard.onrender.com/registry)
(public leaderboard) or [.../assess](https://responsibleai-dashboard.onrender.com/assess)
(self-assess any model/tool). Source, MIT-licensed:
[https://github.com/Guruprasath-Annadurai/Whitepact](https://github.com/Guruprasath-Annadurai/Whitepact).
PyPI: `pip install rai-governance-platform`.

Happy to answer questions about the architecture, the decision
provenance model, or what's still missing (no formal third-party
accreditation yet, no confidence intervals on point-estimate scores —
both stated plainly in the docs, not hidden).

---

## LinkedIn

I spent the last several months building something I kept wishing
existed while working with AI agents: a way to actually check, in
code, whether a specific AI system or agent action is safe, fair,
compliant, and accountable — instead of either an informal "trust us"
claim or a regulatory framework too broad to act on programmatically.

**WhitePact** is now live: an open governance and trust layer for AI
systems and agents.

What it does:
→ A deterministic 5-way governance decision for agent actions (allow,
redact, require approval, deny, or quarantine) — no LLM in the loop
deciding whether to trust another LLM.
→ A 6-dimension Trust Score (fairness, privacy, security, robustness,
compliance, authenticity) — open specification, open reference
implementation, so the published score can never drift silently from
what the code actually computes.
→ PII and harmful-content guardrails, hallucination detection, and
compliance mapping against NIST AI RMF, the EU AI Act, and ISO 42001.
→ A public, verifiable Trust Index — free self-assessment, a
cross-model leaderboard built from actually calling each model's API
(not self-reported), and a public API to check any cited score.
→ An MCP server with 27 governance tools, so any MCP-compatible AI
assistant can call into it directly.

The part I care most about: every self-assessed score is explicitly
labeled as such — `certified: false` — everywhere it's shown. A
citable trust standard is only useful if it can't be quietly gamed
into looking like independent verification.

It's open source (MIT), live, and free to try:
🔗 Try the public leaderboard/self-assessment:
https://responsibleai-dashboard.onrender.com/registry
🔗 Source: https://github.com/Guruprasath-Annadurai/Whitepact
🔗 `pip install rai-governance-platform`

Would genuinely value feedback from anyone building or governing AI
agents in production — what's missing, what would make this something
you'd actually rely on.

#AIGovernance #ResponsibleAI #OpenSource #AIAgents #MCP
