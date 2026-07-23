# MCP Distribution Guide — Getting `responsibleai-mcp` in Front of Corporate AI Teams

> This is the zero-cost, founder-time-only distribution lever from
> `STRATEGY_ROADMAP.md` Part 0, Item 1. It splits into two halves: what this
> repo needed to be *submission-ready* (fixed here) and what actually
> requires the founder to go create accounts and submit — those steps are
> listed as a checklist, not automated, because they involve external
> services this session has no access to and, per this project's own
> standing policy, should not create accounts on your behalf.

Last reviewed: 2026-07-23 · Platform version: 1.2.0

---

## 1. What was wrong before this pass (fixed)

The README's MCP section claimed **10 tools and 5 resources** — the actual
count as of this version is **26 tools and 10 resources**
(`src/responsibleai/mcp/tools.py`, `src/responsibleai/mcp/resources.py`).
This mattered specifically for directory submission: most MCP
directories pull their listing copy directly from a project's README or ask
for a short description you write once — submitting a stale, undercounting
description would have under-sold the server on every single listing
simultaneously. Fixed in this pass: README's overview table, ASCII diagram,
full tool table (all 26, not a sample of 10), and full resource table (all
10). `STRATEGY_ROADMAP.md`'s Part 1 audit table had the same staleness
("15+ governance tools") — also fixed, since that document explicitly
states it's "verified against the current codebase, not marketing copy."

**Before submitting anywhere, re-run this check** — it's cheap and catches
exactly this class of drift:

```bash
grep -c 'name="' src/responsibleai/mcp/tools.py       # tool count
grep -c 'uri=' src/responsibleai/mcp/resources.py     # resource count
```

If either number in a listing/README doesn't match, fix the doc before the
directory submission, not after.

---

## 2. Submission-ready assets (what a directory listing will ask for)

Have these ready, copy-paste, before starting Section 3's checklist:

- **Name**: ResponsibleAI Governance MCP Server (`responsibleai-mcp`)
- **One-line description**: "AI governance MCP server — trust scoring,
  guardrails, hallucination detection, bias evaluation, and NIST AI RMF /
  EU AI Act / ISO 42001 compliance checks for any MCP client."
- **Install command**: `pip install "rai-governance-platform[dashboard,mcp]"`
- **Repository URL**: the GitHub repo's public URL
- **License**: MIT (see `LICENSE`) — most directories filter or highlight
  this; MIT is a strong, unambiguous answer.
- **Category tags** (use whichever a given directory supports): AI
  governance, compliance, security, observability, LLMOps.
- **Transport**: stdio (`responsibleai-mcp`) and HTTP+SSE
  (`responsibleai-mcp-http`, Bearer-authenticated, plan-gated) — some
  directories distinguish these; list both since both are real.
- **Screenshot/demo**: the dashboard's `/` overview page or the `/verify/{id}`
  Trust Passport page make the strongest visual — governance tooling is
  otherwise hard to screenshot meaningfully. Take a fresh screenshot against
  a running local instance before submitting anywhere that accepts one.
- **Honest maturity statement, if a directory asks**: self-hosted,
  open-source core (MIT), no SOC2/pentest yet (see
  `compliance/SOC2_READINESS.md` and `compliance/INTERNAL_SECURITY_REVIEW.md`
  if a reviewer wants detail) — don't oversell certification status a
  directory reviewer could trivially check by asking for the report.

---

## 3. Where to actually submit — founder checklist

Each of these requires creating an account and/or opening a PR on an
external service. None of this can be done on your behalf — check each box
as you complete it:

- [ ] **Anthropic's official MCP server directory/examples repo** — the
  canonical listing corporate Claude Code/Desktop users actually browse.
  Check `github.com/modelcontextprotocol` for the current servers
  directory and its contribution guidelines (these change; read the
  current `CONTRIBUTING.md` there rather than assuming a fixed process).
- [ ] **Community MCP directories/marketplaces** (e.g., Glama, mcp.so-style
  aggregators, PulseMCP, or whatever the current landscape includes by the
  time you do this — the MCP directory ecosystem is new and shifting, so
  search "MCP server directory" freshly rather than trusting a fixed list
  written into this document once and left stale).
- [ ] **Smithery** (or an equivalent MCP hosting/discovery platform, if one
  is current) — some of these also offer one-click install flows for end
  users, which lowers the friction from "found it" to "using it" further
  than a plain GitHub link does.
- [ ] **Your own README's badge/shields** — add a "Listed on [Directory]"
  badge once accepted; this compounds credibility for the *next* directory
  reviewer who checks whether you're listed elsewhere already.
- [ ] **A short launch post** on wherever your existing audience already is
  (a personal blog, LinkedIn, Hacker News "Show HN" if genuinely
  applicable) — timed to coincide with the first directory acceptance, not
  before, so there's already at least one third-party listing to point to.

**Sequencing note**: submit to the official Anthropic-adjacent directory
first if you can identify it — being listed there lends credibility to
every subsequent community-directory submission, the same "the more
official the first placement, the easier the rest" pattern that applies to
press coverage.

---

## 4. What this does and doesn't unlock

Directory listing is **pure top-of-funnel distribution** — it makes the
server *discoverable* by a corporate AI team already looking for MCP-based
governance tooling. It does not, by itself:
- Bypass an enterprise security review for a paid tier (that's still
  `compliance/SALES_TARGETING.md`'s segmentation problem).
- Substitute for the OEM/white-label motion (`STRATEGY_ROADMAP.md` Part 0
  Item 2) — a directory listing gets you *discovered*, not *integrated*.

Track it as a top-of-funnel metric (directory listing → GitHub stars/pip
installs → inbound emails), not a revenue metric directly — Part 4 of
`STRATEGY_ROADMAP.md`'s discipline rule ("who pays for this, and how much")
applies here too: directory listing's answer is "it feeds Phase 1's design
partner pipeline," not "it directly bills anyone."
