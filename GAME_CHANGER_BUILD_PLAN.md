# Game-Changer Build Plan — phase by phase, engineering-level

> Turns `GAME_CHANGER_STRATEGY.md`'s four phases (A: free/public/citable,
> B: agent-native trust-check, C: monetize the layer, D: become the
> reference) into concrete, buildable work against the actual codebase.
> No SOC2, no pentest-as-sales-prep, no early sales hire — per the
> correction that those aren't early-stage requirements. Each phase ends
> with a real, observable outcome, not just "shipped code."

Grounded in what already exists as of v1.2.0:
`src/responsibleai/trust/badge.py` (badge SVG generation),
`src/responsibleai/trust/passport.py` + `db/passport_repository.py`
(Trust Passports), `src/responsibleai/mcp/tools.py` (27 MCP tools
already registered, dispatched via `dispatch_tool()`), and the public
`/verify/{id}` page in `dashboard/app.py`.

**Status as of 2026-07-25**: Phase A items 1-4 shipped (this commit).
Phase B shipped in the prior session — `rai_check_trust` MCP tool,
`GET /api/trust-index/check`, and the LangChain/LangGraph/ADK adapters
under `src/responsibleai/integrations/` are all real, tested code (see
that section below for detail, kept as originally written since it's
now a record of what was built, not a forward plan).

---

## Phase A — "Free, public, citable" — shipped 2026-07-25, items 1-4

**Goal**: the badge/registry loop actually runs, and the public pages
are structured so AI answer engines can cite them.

1. **Un-gate what's currently paid-only — done.** `GET /assess` is a
   public, zero-signup HTML form (`dashboard/static/assess.html`)
   posting to the already-free `POST /api/trust-index/assess` — no API
   key, no account, a citable badge in one page load. Verified live: a
   real submission through the rendered form returned `201 Created` and
   immediately showed up in the registry.
2. **Public Trust Registry page — done.** `GET /registry`
   (`dashboard/static/registry.html`) is a searchable, client-side
   filterable directory over a new `GET /api/trust-index/registry`
   endpoint (backed by `PassportRepository.list_recent()`) — every
   assessed model/tool, certified and self-reported, not just the
   curated `/certified` list. Reuses the same self-contained page
   pattern as `leaderboard.html`/`verify.html`, not a new stack.
3. **Badge embed flow, one-click — done**, and extended: `verify.html`
   already had the copy-embed-code panel from v1.2.0; `assess.html`
   reuses the identical panel so the embed code appears immediately
   after scoring, not just when revisiting `/verify/{id}` later.
4. **Citability pass — done.** JSON-LD added to `verify.html`
   (`schema.org/Review` wrapping a `Rating`) and `registry.html`
   (`schema.org/ItemList`), both populated from live data client-side.
   `GET /llms.txt` now exists, pointing AI crawlers/answer engines at
   the registry, leaderboard, incident DB, free self-assessment, the
   machine-readable APIs, and the open specs.
5. **Directory submissions — not done, needs the user.** Actually
   submitting to MCP/agent-tool directories means creating accounts on
   third-party platforms, which this agent cannot do autonomously (see
   the standing rule against creating third-party accounts). The guide
   is ready at `compliance/MCP_DISTRIBUTION_GUIDE.md` — this is a
   founder action item, not an engineering one.

**Phase A is done when**: a stranger can go from "never heard of this"
to "has an embedded badge on their own site" in under 5 minutes, with no
signup, and the registry/incident pages are live and indexable. Items
1-4 meet that bar as of this commit; item 5 (actual distribution) is
the one open action, and it's on the founder, not this codebase.

---

## Phase B — "The trust-check other agents call" (target: 6-10 weeks after A)

**Goal**: `responsibleai-mcp` becomes a standalone primitive other agent
frameworks integrate, not just a tool ResponsibleAI's own dashboard uses.

1. **Extract a minimal "trust-check" MCP tool** distinct from the
   existing 25 (`rai_scan`, `rai_trust_score`, etc., in
   `mcp/tools.py`). Those are built for *evaluating your own model's
   outputs*. The new primitive answers a different question: *"should I
   (an agent) trust this third-party tool/MCP server/model before
   invoking it?"* — call it `rai_check_trust` — takes a model/tool
   identifier, returns the public Trust Index score + certification
   status + any open incidents, with **no auth required** for the basic
   check (rate-limited, not gated).
2. **Ship it as an installable package other MCP hosts can add in one
   line** — publish `responsibleai-mcp` (already has
   `responsibleai-mcp` / `responsibleai-mcp-http` entry points in
   `pyproject.toml`) to the MCP registries targeted in Phase A's
   directory submissions, with a README example showing "add this one
   server, get a trust gate on every tool call" — the actual `npm
   audit`-for-agents pitch, made concrete in code a framework maintainer
   can copy in minutes.
3. **A tiny reference integration**, built and open-sourced, showing
   `rai_check_trust` wired into a popular agent-loop pattern (e.g., a
   LangChain or plain-MCP-client example that refuses to call a tool
   scoring below a threshold). This is a marketing artifact as much as
   code — "here's proof it works," not just an API spec.
4. **Spec v1.0 publication.** Take `compliance/TRUST_INDEX_SPEC.md` from
   internal doc to a versioned, externally-contributable spec: a public
   changelog, a clear "how to propose a change" path, and a stable
   version number referenced by the API (`trust-index/v1`) so downstream
   integrators aren't tracking a moving target.

**Phase B is done when**: at least one agent framework or MCP host that
isn't ResponsibleAI's own dashboard has integrated `rai_check_trust` —
or, if that hasn't happened yet, when the reference integration exists
and outreach to 10-20 framework maintainers has actually happened (not
just "the tool exists and nobody's been told").

---

## Phase C — "Monetize the layer" (only after A and B show real usage)

**Explicit gate, not a calendar date**: don't start Phase C on a
timer — start it when Phase A/B produce real numbers (badge embeds by
people who weren't asked to, MCP tool calls from outside the project, at
least one unprompted external reference). If those numbers aren't there
after a reasonable run, this is the point to reassess, not push forward
on hope (same discipline `GAME_CHANGER_STRATEGY.md` Section 7 states).

1. **Paid tiers on top of what's already free**: higher-rate-limit API
   access to `rai_check_trust`, human-reviewed "Certified" badge tier
   (already spec'd — `POST /api/trust-index/certify/{id}` exists,
   currently manual/founder-reviewed; this is where a lightweight
   reviewer workflow gets built, not before).
2. **OEM/white-label** (`compliance/OEM_LICENSING.md` already drafted)
   — now pitched with real usage numbers instead of a cold deck.
3. **Only now** does the enterprise motion from `STRATEGY_ROADMAP.md`
   Phase 2 and `VERSION_ROADMAP.md` v3.0.0 become worth revisiting — and
   only the parts a real inbound enterprise lead actually asks for
   (SOC2 included, opportunistically, per the correction — not upfront).

---

## Phase D — "Become the reference" (ongoing, compounds from A+B+C)

Same destination as `VERSION_ROADMAP.md` v5.0.0/v6.0.0 — insurance
underwriting recognition, regulatory citation, multi-jurisdiction
coverage — reached because the registry/incident DB/leaderboard already
have real usage and citations behind them, not because enough enterprise
seats were sold to fund a compliance department. No new build items
here beyond what A-C already produce; this phase is about outreach and
partnership work (insurers, regulators, researchers), not code.

---

## What this means for right now, concretely

The very next engineering task, if this plan is adopted, is **Phase A
item 1-2**: remove the signup requirement from the free trust
assessment flow and ship the public `/registry` page. That's a scoped,
buildable next step — say the word and it can be broken into a task
list against the actual `dashboard/app.py` routes and `passport_repository.py`
queries.
