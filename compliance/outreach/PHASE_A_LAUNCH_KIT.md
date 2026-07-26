# Phase A Launch Kit — outreach and directory-submission copy

> Drafts only, same policy as `READY_TO_SEND_EMAILS.md`: Claude does not
> post, submit, or message on your behalf. Everything here is ready to
> copy-paste, but you create the accounts, click submit, and post it
> yourself. Fill in bracketed placeholders before sending anything.
>
> This exists because `GAME_CHANGER_STRATEGY.md`'s bet only works if
> people who aren't in this conversation actually see the badge/registry/
> trust-check — as of this writing the registry is live and empty. This
> kit is the fix for that, not more code.

Last reviewed: 2026-07-26 · Platform version: 1.2.0 (27 MCP tools, 10 resources)

---

## 1. Show HN post

Timing note from `compliance/MCP_DISTRIBUTION_GUIDE.md` Section 3: post
this *after* at least one directory listing is accepted, not before —
"already listed somewhere" is worth more credibility than posting first.

**Title** (HN strips most punctuation and has a length limit — this fits):

```
Show HN: An open trust registry for AI models/tools, plus an MCP tool agents can call before trusting one
```

**Body**:

```
I built ResponsibleAI (MIT-licensed) — a free, public Trust Index for AI
models and tools: self-assess for free, get a citable score and an
embeddable badge, no signup. https://responsibleai-dashboard.onrender.com/registry

The part I actually want feedback on: an MCP tool (`rai_check_trust`)
that lets an agent check a third-party model or tool's trust score
*before* invoking it — plus adapters for LangChain (a `wrap_tool_call`
middleware that blocks a low-trust call), LangGraph (a node that pauses
with `interrupt()` for a human decision instead of a hard block), and
Google ADK (which auto-discovers the MCP server's tools with zero glue
code). Source and the three adapters:
https://github.com/Guruprasath-Annadurai/ResponsibleAi/tree/main/src/responsibleai/integrations

Also has a public leaderboard (measured live against a published prompt
corpus, not self-reported) and a crowd-reported AI incident database,
hash-chained so entries can't be silently edited after publication.

Everything free/public stays free — no signup wall on the registry,
leaderboard, incident DB, or the basic trust-check. Full methodology is
published, including what's honestly *not* measured yet (see
compliance/TRUST_INDEX_SPEC.md and compliance/LEADERBOARD_METHODOLOGY.md
in the repo) — I'd rather state the gaps than round up.

Solo project, not VC-backed, genuinely want to know if the agent-trust-
check idea is useful to anyone building with LangChain/LangGraph/ADK
right now, or if I'm solving a problem nobody has yet.
```

---

## 2. LangChain / LangGraph GitHub Discussions post

Post in the relevant "Show and tell" / "Ideas" discussion category on
`github.com/langchain-ai/langchain` and `github.com/langchain-ai/langgraph`
separately — tailor the second paragraph per repo (middleware for
LangChain's discussion, the `interrupt()` node for LangGraph's).

**Title**: `TrustGateMiddleware / a trust-gate node for tool calls — feedback wanted`

**Body**:

```
Posting here because I built this against your actual 1.x middleware API
(wrap_tool_call) rather than the older on_tool_start callback, which I'd
initially assumed could block execution and turned out — correctly, per
your docs — to be observer-only.

What it does: before a tool call executes, it checks the tool's public
ResponsibleAI Trust Index score and either lets it through, blocks it
(LangChain: TrustGateMiddleware), or pauses for a human approve/reject
decision via interrupt() (LangGraph: make_trust_gate_node()). Fails open
by default on network errors or an unassessed tool, since a fail-closed
default would block every unscored tool call out of the box.

Source: https://github.com/Guruprasath-Annadurai/ResponsibleAi/blob/main/src/responsibleai/integrations/langchain_middleware.py
(and .../langgraph_gate.py)

Genuinely asking, not just announcing: is "check a tool's trust score
before calling it" a real pattern people want, or is there already a
better-established convention for this in the ecosystem I should be
building against instead? Happy to adjust the integration if there's a
more idiomatic shape for it.
```

---

## 3. Google ADK GitHub Discussions post

Post on `github.com/google/adk-python` (or `adk-docs`, whichever repo's
discussions are more active at the time).

**Title**: `MCPToolset + a free public trust-check MCP server — quick example`

**Body**:

```
Small example in case it's useful to anyone: I pointed McpToolset at an
existing MCP server (responsibleai-mcp, 27 tools) and it picked up a new
`rai_check_trust` tool with zero custom code — the auto-discovery via
list_tools just worked, which was the whole appeal of trying ADK for
this over hand-rolling a tool wrapper.

rai_check_trust looks up a free, public trust score for a third-party
model or tool by name — meant for an agent to call before invoking
something it doesn't already know to trust.

Factory functions + a working example:
https://github.com/Guruprasath-Annadurai/ResponsibleAi/blob/main/src/responsibleai/integrations/adk_toolset.py

Mostly sharing because "point McpToolset at a real free MCP server and
it just works" felt like a good sign for MCP tools in ADK generally —
curious if others have hit friction points I got lucky avoiding.
```

---

## 4. MCP directory submission copy

Pulled forward from `compliance/MCP_DISTRIBUTION_GUIDE.md` Section 2,
updated with what shipped since that doc was last reviewed (the
`rai_check_trust` tool and the three framework integrations) — use this
version, not the older one, since directory listing copy should reflect
the current 27-tool count and the new agent-integration angle.

- **Name**: ResponsibleAI Governance MCP Server (`responsibleai-mcp`)
- **One-line description**: "AI governance MCP server — trust scoring,
  guardrails, hallucination detection, bias evaluation, NIST AI RMF / EU
  AI Act / ISO 42001 compliance checks, and a free trust-check tool
  (`rai_check_trust`) for gating agent tool calls on a third party's
  public trust score."
- **Install command**: `pip install "rai-governance-platform[dashboard,mcp]"`
- **Agent-framework integrations** (worth its own line on directories
  that support one): LangChain, LangGraph, and Google ADK adapters —
  `pip install "rai-governance-platform[agent-frameworks]"`.
- **Repository URL**: `https://github.com/Guruprasath-Annadurai/ResponsibleAi`
- **License**: MIT
- **Category tags**: AI governance, agent safety, compliance, security,
  observability, LLMOps
- **Transport**: stdio (`responsibleai-mcp`) and HTTP+SSE
  (`responsibleai-mcp-http`)
- **Screenshot/demo**: `/registry` (the new public directory) or
  `/verify/{id}` — take a fresh screenshot against the live instance
  before submitting: `https://responsibleai-dashboard.onrender.com/registry`
- **Honest maturity statement, if asked**: self-hosted, open-source core
  (MIT), no SOC2/pentest yet — see `compliance/SOC2_READINESS.md` and
  `compliance/INTERNAL_SECURITY_REVIEW.md` if a reviewer wants detail.

Checklist of where to actually submit is unchanged from
`compliance/MCP_DISTRIBUTION_GUIDE.md` Section 3 — this section only
refreshes the copy you paste into each one, not the list of where.

---

## 5. What to do after any of this lands

Update this file's checklist below as things actually happen — this is
the only honest way to know if `GAME_CHANGER_STRATEGY.md` Section 7's
"reasonable window" has started, since the clock doesn't start until step
1 actually happens.

- [ ] First directory submission accepted (date: ______)
- [ ] Show HN posted (date: ______, link: ______)
- [ ] LangChain/LangGraph discussion posted (date: ______, link: ______)
- [ ] ADK discussion posted (date: ______, link: ______)
- [ ] First unprompted external badge embed spotted (date: ______, where: ______)
- [ ] First unprompted external `rai_check_trust` / MCP server use spotted (date: ______, where: ______)
