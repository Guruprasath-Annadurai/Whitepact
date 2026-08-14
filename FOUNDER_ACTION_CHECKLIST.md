# Founder Action Checklist

> Every item below requires the founder personally — an account creation,
> an external submission, a real conversation, or a legal/financial
> decision — none of which Claude can do on your behalf (see this
> project's standing policy against creating accounts or executing
> financial actions for you). This consolidates every such item flagged
> across `STRATEGY_ROADMAP.md`, `compliance/MCP_DISTRIBUTION_GUIDE.md`,
> `compliance/OEM_LICENSING.md`, `compliance/COMPLIANCE_STARTER_KIT_OFFER.md`,
> `compliance/INSURANCE_PARTNERSHIP_PITCH.md`,
> `compliance/TRUST_INDEX_PAPER.md`, `compliance/SOC2_READINESS.md`,
> `compliance/INTERNAL_SECURITY_REVIEW.md`, `DEPLOY_RUNBOOK.md`, and the
> legal drafts — one place to work through, instead of six documents.
>
> Nothing here is ordered by urgency for you specifically — work top to
> bottom or pick whatever's cheapest/fastest for your own situation.
> Check items off in this file directly as you complete them; it's a
> tracker, not a one-time read.

Last reviewed: 2026-07-23

---

## 1. MCP distribution (zero cost — founder time only)

*Source: `compliance/MCP_DISTRIBUTION_GUIDE.md`*

- [ ] **Multi-platform onboarding prep — done 2026-08-13, submissions
      still open**: built `docs/integrations/` (compatibility matrix +
      9 per-platform setup docs), `examples/` configs for Grok/Gemini/
      Amazon Q/AWS AgentCore, `.cursor-example/mcp.json`,
      `docs/adr/ADR-MISTRAL-MCP-TRANSPORT.md`, `distribution/microsoft/`
      certification prep package, and `scripts/integration_smoke.py`
      (live-verified against the hosted endpoint, all 5
      `LOCAL_PROTOCOL_TEST` checks passing). Full breakdown of what
      still needs you, grouped by action type, in
      `docs/integrations/FOUNDER_ACTIONS.md` — highlights: GitHub
      Copilot CLI and Claude's connector UI need a live session to
      confirm (not automatable here); Grok/Gemini examples need
      `XAI_API_KEY`/`GEMINI_API_KEY` to run for real; Microsoft
      certification needs Partner Center + business verification
      (blocked on Radtech LLP not yet being incorporated — see
      [[project_radtech_llp_startup]]); Mistral has no confirmed
      official submission channel (only an unofficial community repo
      was found — did not treat it as authoritative).
- [x] **Grok live-verification — DONE 2026-08-14**: full round trip
      (connect, auth, tool discovery, `rai_scan` tool call, structured
      response) succeeded against the live xAI API with real
      credentials. The response was WhitePact's own correct FREE-plan
      gating (`hosted_access_unavailable`) — genuine proof the
      integration works end to end, not a config check. Three real bugs
      found and fixed along the way: (1) wrong `WHITEPACT_API_KEY` — a
      dashboard OWNER key was mistakenly used instead of an org-scoped
      key from `POST /api/orgs/{id}/keys`; (2) the bearer token belongs
      in the OpenAI SDK's dedicated `authorization` field, not `headers`;
      (3) [Gemini's two bugs, see below]. See `docs/integrations/grok.md`
      for full detail, plus new research on public discoverability:
      `grok.com/connectors`' curated catalog has no public submission
      path found; `xai-org/plugin-marketplace` is a real, official,
      PR-based process but for Grok Build (coding agent), not the chat
      connector catalog.
      **Submitted 2026-08-14**:
      [xai-org/plugin-marketplace#244](https://github.com/xai-org/plugin-marketplace/pull/244)
      adds WhitePact as a local plugin (MCP server config + skill),
      passed all local validation scripts and all 3 of xAI's automated
      PR checks. Awaiting xAI code-owner review — see
      `docs/integrations/FOUNDER_ACTIONS.md` for full detail.
- [ ] **Gemini live-verification — attempted 2026-08-14,
      billing-blocked**: found and fixed two genuine bugs (wrong API
      method, a model name deprecated for new users despite still
      appearing in the SDK's own type hints) — after the fix, the tool
      config is confirmed accepted by the live Gemini server. Blocked
      purely on account billing: `429` requiring a billing-enabled
      Google Cloud project. See `docs/integrations/gemini.md` for full
      detail.
      **Two compromised secrets from this work, neither rotated yet**:
      (1) a `RAI_API_KEY` (OWNER-role dashboard key, pasted into chat
      while creating a test org) — **rotate in Render →
      responsibleai-dashboard → Environment →
      `RAI_API_KEYS`/`WHITEPACT_API_KEYS`, then click Save, rebuild, and
      deploy**; (2) a scoped `WHITEPACT_API_KEY` (visible in an SDK
      response repr during the successful Grok test) — **rotate via a
      fresh `POST /api/orgs/{id}/keys` call**. Neither has been done as
      of this entry.
- [x] **Post-push CI green-up — done 2026-08-13**: the multi-platform
      onboarding push above surfaced a pre-existing red `main` (from
      before this session) — fixed, not silenced:
      - `test_version_matches_pyproject` was asserting `server.json`'s
        top-level *and* `packages[0]` version both equal
        `pyproject.toml` exactly, which made the intentional
        listing-vs-published-package version split undoable without a
        real PyPI release. Bumped `pyproject.toml` (and
        `responsibleai.__version__`, kept in lockstep by its own
        drift-guard test) to `1.2.3` to match the registry listing, and
        replaced the equality check with two directional invariants:
        the published package version can never be ahead of
        `pyproject.toml`, and the listing version can never fall behind
        the package it describes. `packages[0].version` stays at
        `1.2.2` — the real, currently-published PyPI release; `1.2.3`
        has not been published (confirmed live against PyPI's API).
      - `Self-Conducted Security Scan` (Bandit) was failing on B104
        (`hardcoded_bind_all_interfaces`) in
        `src/responsibleai/mcp/server.py`'s `main_http()` — the
        `0.0.0.0` default bind, unchanged since 2026-07-09, so also
        pre-existing. Added a scoped, justified `# nosec B104` (not a
        blanket rule exclusion) with a comment explaining why: the
        process runs in a Render container that requires binding all
        interfaces to be reachable, and the actual security boundary is
        the Bearer-key auth plus `RAI_MCP_HTTP_ALLOWED_ORIGINS`/
        `ALLOWED_HOSTS`, not the bind address.
      - Verified live on GitHub: `CI`, `Self-Conducted Security Scan`,
        and `OpenSSF Scorecard` all green on commit `6764ee7` before
        calling this closed — not just "should pass," actually
        confirmed via `gh run list`.

- [x] Submit to the official MCP registry — **done and live 2026-08-12**:
      published as `io.github.Guruprasath-Annadurai/whitepact` v1.2.2 via
      `mcp-publisher`, confirmed queryable at
      `registry.modelcontextprotocol.io/v0/servers?search=whitepact`.
      Took 3 patch releases (1.2.0→1.2.2) to land: PyPI's README-based
      `mcp-name` ownership marker and the GitHub-OAuth namespace check
      are both case-sensitive, and the original `server.json` used
      all-lowercase where the actual GitHub account is
      `Guruprasath-Annadurai` — see `CHANGELOG.md`'s 1.2.2 entry.
- [ ] Glama — **still not indexed as of 2026-08-14**: re-checked, this
      time against their actual API
      (`glama.ai/api/mcp/v1/servers?query=whitepact`, not just the
      JS-rendered page) — `{"servers": []}`, a clean zero-match result,
      out of 72,352 total servers in their registry. No public
      submission form without their own account login; likely just
      needs more time for their crawler to pick up the official
      registry listing. Check back again in another week or two, or
      sign in and use their "Add Server" flow directly if it's still
      unlisted by then.
- [x] PulseMCP — **no action needed**, confirmed live 2026-08-13:
      their own `/submit` page states plainly *"if you have a server to
      share, publish it to the Official MCP Registry... we will pick it
      up automatically once we are back."* WhitePact is already on the
      official registry, so once their submissions-paused period ends
      (their page says "until mid-August" — essentially now), no manual
      submission is required at all.
- [x] Submit to Smithery — **done and live 2026-08-12**: listed as
      `guruprasathannadurai-official/whitepact`, 27 tools + 20 resources
      discovered. Required real infra work, not just a form: this
      deployment had no separate hosted MCP HTTP transport at all (the
      dashboard only serves REST), so a second Render service
      (`whitepact-mcp-http`, running `responsibleai-mcp-http`) was
      created to actually host `/mcp` publicly. Smithery's scanner then
      hit an OAuth-discovery dead end (this deployment only supports
      static Bearer API keys, no OIDC configured) — fixed by adding a
      public `/.well-known/mcp/server-card.json` endpoint serving the
      same live TOOL_DEFS/RESOURCE_DEFS the server itself advertises,
      per Smithery's own documented fallback for auth-required servers.
- [x] Add "Listed on [Directory]" badges to the README — **done**:
      MCP Registry and Smithery badges added 2026-08-12.
- [x] Write a short launch post (blog, LinkedIn, "Show HN" if applicable)
      now that both listings are live — **drafted 2026-08-14**:
      `compliance/outreach/LAUNCH_POST_DRAFT.md`, a Show HN variant, a
      LinkedIn variant, and an X (x.com) thread variant (7 tweets,
      character-counted against X's 280-char limit), same underlying
      facts framed for each audience. Every claim (dashboard,
      `/registry`, `/assess`, PyPI) checked live (HTTP 200) before
      drafting — nothing aspirational. X has no app-directory analogous
      to a plugin marketplace — "displaying WhitePact on X" means
      posting from your own account, which is what this draft is for.
      You only need to review and post.
- [x] OpenAI — **checked live 2026-08-13**: no public directory to
      submit to. ChatGPT/Codex reach an MCP server via per-organization
      "Connectors" config — a customer manually points their own
      instance at your `/mcp` URL (`platform.openai.com`'s MCP-server
      guide describes building/connecting one, not a central listing).
      Nothing to submit; this already works today via the live hosted
      endpoint.
- [x] Google — **checked live 2026-08-13**: same shape as OpenAI.
      Gemini Enterprise has a "set up your custom MCP server data
      store" flow — a per-org admin connects a custom MCP server
      manually, no central directory. Nothing to submit here either.
- [ ] Anthropic — **checked live 2026-08-13, genuinely different from
      OpenAI/Google**: Claude's **Custom Connectors** (bring-your-own
      URL) already works today with zero action, same as the others —
      any user can paste `https://whitepact-mcp-http.onrender.com/mcp`
      into their own Custom Connectors settings right now. But
      Anthropic *also* runs a real, curated, in-app **Connectors
      Directory** with its own actual submission/review process (an
      "Anthropic Software Directory Policy" and a verification step,
      per their own help center) — this is the one directory of the
      four that genuinely needs a founder action. The submission entry
      point lives behind Claude Console login (`console.claude.com`),
      which needs your own account — search the Console for
      "Connectors Directory" or "Submit a connector" once logged in.
- [x] **Resolved 2026-08-13**: OpenAI Plugins Directory submission —
      WhitePact v1.2.3 submitted for review, confirmed both in-app and
      via a real confirmation email from OpenAI. Full path completed:
      Individual identity verification, domain ownership verification
      (built a `/.well-known/openai-apps-challenge` route serving a
      portal-issued token), all 27 tools scanned with annotations and
      per-tool justifications, 5 starter prompts, 5 positive + 3
      negative test cases, a Developer-Mode demo recording
      (`https://youtu.be/PkVZ5Kq6zrU`), Allowed Countries set to all
      (a real risk given the privacy policy/terms are still
      self-drafted, not attorney-reviewed — flagged to the founder,
      founder's explicit choice to proceed anyway).
      **Notable engineering byproduct**: this submission required a
      demo-only unauthenticated-access bypass
      (`RAI_MCP_HTTP_ALLOW_UNAUTHENTICATED_DEMO`) on
      `whitepact-mcp-http`, since neither ChatGPT's Developer Mode
      connector UI nor the OpenAI submission portal's own MCP auth
      picker (OAuth / No Auth / Mixed only) support a static Bearer
      API key — the same real gap flagged for the Anthropic submission
      above. The bypass was enabled twice (for the demo recording, and
      separately for the portal's "Scan Tools" step), verified active
      before each use and verified reverted to `401 unauthorized`
      immediately after both times — never left open. Building real
      OAuth 2.1 support for `whitepact-mcp-http` remains open, larger
      work, deferred by choice (see `compliance/CONNECTOR_READINESS_REPORT.md`).

## 2. OEM/white-label outreach (zero cost — founder time only)

*Source: `compliance/OEM_LICENSING.md`, draft email in
`compliance/outreach/READY_TO_SEND_EMAILS.md` Section 1*

- [x] Identify 5-10 named agent-platform startups as OEM prospects —
      **done 2026-08-12**: CrewAI, Relevance AI, Lyzr, StackAI,
      Cognosys, Orby AI, TrueFoundry. See `compliance/OEM_LICENSING.md`
      Section 5a for rationale per company; confirm each still fits
      before outreach, this space moves fast.
- [ ] Fill in and send the drafted outreach email to each — content is
      ready, recipient research is now done, sending is yours (find a
      named contact per company, don't use a generic contact form).
- [ ] Have an actual OEM license agreement drafted by an attorney before
      any real deal closes — the one-pager is a conversation starter only.
- [ ] Update Section 4's pricing anchors once a real deal closes somewhere
      different from the starting numbers.

## 3. Compliance starter kit sales (zero cost to start)

*Source: `compliance/COMPLIANCE_STARTER_KIT_OFFER.md`, draft email in
`compliance/outreach/READY_TO_SEND_EMAILS.md` Section 2*

- [ ] Quote the starter kit to 3 companies in your own network first, at a
      founding-customer discount, before publishing any public price.
- [x] Have a simple one-page scope-of-work ready before taking a real
      payment — **done 2026-08-14**:
      `compliance/starter-kit/SCOPE_OF_WORK_TEMPLATE.md`, fill-in-the-
      blank, covers both paid tiers (Guided fill-in, Full consulting),
      states plainly what's not included (not a certification, not
      legal advice, not an audit of the client's actual security
      posture) before any payment changes hands. Smoke-tested
      `scripts/generate_compliance_kit.py` while drafting this — it
      still scaffolds both templates exactly as described, generates
      real output.
- [ ] Update the pricing table once a real engagement closes at a
      different number.

## 4. Insurance/underwriting outreach (one afternoon, long-shot)

*Source: `compliance/INSURANCE_PARTNERSHIP_PITCH.md`, draft email in
`compliance/outreach/READY_TO_SEND_EMAILS.md` Section 3*

- [ ] Two real, named candidates found 2026-07-23: **AIUC** (Artificial
      Intelligence Underwriting Company — SF-based, AIUC-1 audit standard
      + Beazley-backed liability coverage; frame as complementary, not
      competing) and **Testudo** (Lloyd's-backed MGA, $10M-$10B revenue
      mid-market focus — likely too large a customer profile to be your
      own prospect, but worth a direct data-partnership pitch anyway).
      Find current contact channels on `aiuc.com` and Testudo's site.
- [x] Search for additional current candidates beyond these two —
      **done 2026-08-12**: **Armilla AI** (Chaucer-backed, up to $25M,
      pairs coverage with independent model verification — same
      competing/complementary framing as AIUC), **Corgi** (full-stack
      AI-native carrier, closer size match to a bootstrapped company
      than Testudo), **Klaimee** (insures autonomous AI agents
      specifically — narrowest product fit of any candidate found),
      **Google Cloud Risk Protection Program** (adjacent, lower
      priority). See `compliance/INSURANCE_PARTNERSHIP_PITCH.md`
      Section 5 for detail.
- [ ] Fill in and send the drafted email to 2-3 targets — Klaimee and
      Corgi are the strongest fits given the researched detail above.
- [ ] Get any real interest confirmed in writing before treating it as a
      partnership or announcing it publicly.

## 5. arXiv publication

*Source: `compliance/TRUST_INDEX_PAPER.md`*

- [x] Convert the Markdown draft to LaTeX — **done 2026-08-14**:
      `compliance/trust_index_paper.tex`, compile-verified with
      `tectonic` (installed locally for this purpose), zero errors,
      zero undefined citations, zero overfull/underfull boxes after
      fixing an `amsmath` omission and a `\texttt{}`-can't-break-at-`/`
      issue. Rendered pages checked visually (title/abstract, table,
      bibliography). Re-verify current arXiv format requirements
      against it before actually uploading, since these can change.
- [ ] **Confirmed as of arXiv's 2026-01-21 policy update**: an
      institutional email alone no longer qualifies a first-time
      submitter. Without prior authorship on an already-accepted paper in
      `cs.AI`/`cs.CY`, you need a personal endorser (advisor, colleague, or
      existing arXiv author with endorsement privileges) — identify and
      confirm that person *before* starting the submission. Cannot be
      done on the founder's behalf.
- [x] Replace every placeholder reference in the paper's References
      section with real, correctly formatted citations — **done
      2026-08-14**: 7 citations (TruthfulQA, BBQ, NIST AI RMF, EU AI
      Act, PCI-DSS, HellaSwag, ISO/IEC 27001) checked live against
      primary sources, not reproduced from memory. Removed one
      originally-listed citation (differential privacy) that turned out
      to have zero actual connection to this paper — it described an
      unrelated feature (`PRIVACY.md`'s "PrivacyLabel"), not the
      PII-detection mechanism the privacy dimension actually uses.
      Added inline `[n]` markers in the body text, which the draft
      previously lacked entirely.
- [ ] Get a second, ideally domain-expert, reader to review the paper
      before submitting — this was written by the same team that built the
      system it describes. Requires a human; not attempted here.
- [x] Re-verify every code file reference in the paper against the
      current codebase — **done 2026-08-14**: all citations checked
      (`trust/score.py`, `trust/passport.py`,
      `db/passport_repository.py`, verify/badge/assess/certify
      endpoints, SHA-256 hash) — everything still matches exactly. Found
      and fixed two real drifts in the process: a missing citation for
      `leaderboard/runner.py` (the code that actually implements the
      paper's "automated measurement" provenance path), and a factual
      error claiming the compliance dimension references GDPR when the
      real code references NIST AI RMF/EU AI Act/ISO 42001. **Re-run
      this check again immediately before actual submission** — code
      moves faster than a paper draft.
- [ ] Create an arXiv account and actually submit.

## 6. Hosted instance — **live, with a real ~17-day outage 2026-07-26 to 2026-08-12**

*Source: `DEPLOY_RUNBOOK.md`, `SLA.md`, `STRATEGY_ROADMAP.md` Part 0*

The plan below (GCP VM + Docker Compose) turned out not to be what
actually got built — GCP's billing setup hit real friction (UPI payment
failures), so the founder pivoted to a card-free managed-services stack
instead.

**Real incident, not a hypothetical**: the Supabase free-tier database
auto-paused from inactivity around 2026-07-26 (Supabase pauses free
projects after ~1 week idle). Every deploy attempt from then through
2026-08-12 — roughly 40 consecutive commits, including several pure
documentation changes with no code touched at all — crashed at startup
with `asyncpg.exceptions.InternalServerError: (ENOTFOUND) tenant/user
... not found`, Supabase's exact pooler error for an unreachable
paused project. Root-caused via Render's deploy logs (a docs-only
commit failing identically to a code commit was the tell that ruled
out anything in the diffs) and Supabase's own dashboard. Blocked on a
second issue while fixing it: the account's other Supabase
organization (`Edora`) already used 2 of 2 free-tier project slots,
so the paused WhitePact project couldn't resume until an unused
project (`edora-staging`) was paused to free a slot. Confirmed
recovered 2026-08-12 via `/api/health` returning `200` with
`database: ok` and the pre-outage org data intact (`orgs: 1` — nothing
lost across the pause). **Action item**: consider Supabase's paid tier,
or a scheduled keep-alive ping, if another multi-week gap between
deploys is likely — free-tier auto-pause will recur otherwise.

What's actually live:

- [x] **Compute**: Render free-tier web service (`responsibleai-dashboard`),
      auto-deploying `Dockerfile` from `main` on every push. Live at
      `https://responsibleai-dashboard.onrender.com`.
- [x] **Database**: Supabase managed Postgres, accessed via its
      transaction-mode pooler (the direct host is IPv6-only and
      unreachable from Render — fixed by using the pooler + a
      `statement_cache_size=0` fix in both `db/engine.py` and
      `migrations/env.py`).
- [x] **Rate-limit backend**: Upstash managed Redis, replacing the
      in-memory limiter (`rate_limit_backend: redis` confirmed via
      `/api/health`).
- [x] Migrations applied, first real org + OWNER key created, bootstrap
      key retired — confirmed to survive a redeploy (proving persistence
      actually works, not just configured).
- [ ] Register or point a real domain/subdomain at the Render service
      (currently only reachable at its `.onrender.com` URL). **This
      just became a hard blocker, not just polish**: CSA rejected the
      2026-08-12 STAR submission specifically because it came from a
      personal Gmail address rather than an organizational domain (see
      Section 9 below) — a cheap domain (~$10-15/yr) plus free email
      forwarding (Cloudflare Email Routing or Zoho Mail's free tier)
      unblocks resubmission with zero new CAIQ content work.
- [ ] Set up a public status page (statuspage.io or equivalent) and link
      it from `SLA.md`.
- [ ] **Now that this is genuinely live**, go back and remove/update the
      "no hosted instance is live yet" caveat in `SLA.md`,
      `TERMS_OF_SERVICE.md`, and `PRIVACY_POLICY.md` — this is now
      inaccurate as written and should reflect the real (free-tier,
      no-custom-domain-yet) status rather than either overclaiming or
      leaving the old "doesn't exist" language standing.
- [ ] **Abandoned**: the GCP project (`responsible-ai-503312`) — either
      delete it to avoid any future billing surprise, or keep it as a
      dormant sandbox; it's not part of the live architecture.
- [x] **Resolved 2026-08-13**: the Supabase database password and
      Upstash Redis token that appeared in plaintext earlier in this
      session's chat history have both been rotated. Real friction
      along the way, worth remembering: (1) Supabase's connection
      string page defaults to the *direct* connection (IPv6-only,
      unreachable from Render) — had to explicitly select "Transaction
      pooler" mode each time; (2) the literal `[YOUR-PASSWORD]`
      placeholder got pasted unsubstituted at one point; (3) Upstash's
      console shows credentials in a `KEY="value"` .env-snippet format
      — pasting that whole line (quotes and variable name included)
      instead of just the bare URL caused a silent crash-loop for
      ~40 minutes with no visible error until the deploy logs were
      checked directly. Confirmed live via `/api/health`:
      `database: ok`, `rate_limit_backend: redis`, prior org data
      intact. `whitepact-mcp-http` has no DB/Redis config at all
      (confirmed empty), so nothing needed rotating there.
- [x] **Resolved 2026-08-13**: `whitepact-mcp-http` now has
      `RAI_DATABASE_URL` and `RAI_REDIS_URL` wired in (the gap flagged
      immediately above, from earlier the same day). Confirmed via a
      genuinely new deploy (build started 20:17:51 UTC, distinct from
      the prior 20:12 UTC deploy that only added `server.json`'s
      `remotes` entry) — clean startup, no `asyncpg` or
      `limits.errors.ConfigurationError` crash, `/health` returning
      `200` continuously afterward. **Honest caveat**: this confirms
      the values are set and didn't break startup — it does not prove
      a real query against Postgres/Redis has actually succeeded yet,
      since `create_engine()` connects lazily and this server (unlike
      `responsibleai-dashboard`'s `/api/health`) doesn't report its DB
      backend on either endpoint. Full confirmation needs an
      authenticated tool call that touches usage/quota tracking once a
      real API key exercises it — treat as "config applied, boot
      verified" rather than "DB read/write verified" until then.
- [ ] **Server.json `remotes` published 2026-08-13** (registry listing
      version 1.2.3): `whitepact-mcp-http.onrender.com` is now listed
      as a real remote MCP transport (`/mcp` streamable-http, `/sse`)
      on the official MCP Registry, not just the stdio package. Live
      per direct registry query (`isLatest: true`, `status: active`).
      Follow-up still open: decide on OAuth 2.1 vs the current
      apiKey-only auth before submitting to Anthropic's Connectors
      Directory — see `compliance/CONNECTOR_READINESS_REPORT.md` §4.
- [x] **Resolved 2026-08-13**: load-tested `whitepact-mcp-http`'s live
      public endpoints directly (no Render access needed for this
      part). Results: 150 concurrent `GET /health` requests → 100%
      success, p95 1.25s; 50 concurrent server-card fetches → 100%
      success; 30 concurrent `POST /mcp` with no API key → correctly
      triggered a Redis-backed auth-failure lockout (`429
      too_many_attempts`) rather than crashing or hanging — incidental
      but real confirmation that `RAI_REDIS_URL` is functioning, not
      just present. Single `WEB_CONCURRENCY=1` worker (Render's
      default for this instance's CPU allocation) held up fine at this
      scale via async I/O. **Caveats, stated plainly**: this is burst
      load from one location over ~1 minute, not sustained/soak-tested
      load, and the 429 response is missing a `Retry-After` header
      (minor client-experience polish, not a correctness bug) — both
      worth revisiting if real connector traffic volume ever
      materializes, but neither blocks a directory submission today.
- [x] **Resolved 2026-08-13**: uptime monitoring added for
      `whitepact-mcp-http` via UptimeRobot (free tier — Render's own
      Hobby plan doesn't include runtime downtime alerting, only
      deploy-failure notifications). Monitor: `GET
      https://whitepact-mcp-http.onrender.com/health` every 5 minutes.
      Alert path verified end-to-end, not just configured — a test
      "DOWN" notification was sent and confirmed received in Gmail
      within the same minute. This closes the "reviewer/admin hits a
      cold or dead endpoint with nobody noticing" gap from the original
      connector-readiness build list.

## 7. Billing (only once selling live)

*Source: `DEPLOY_RUNBOOK.md` step 12*

- [ ] Create live-mode Stripe Prices matching `mcp/licensing.py`'s
      `plan_catalog()`.
- [ ] Add and test the Stripe webhook endpoint in test mode before
      flipping to live keys.

## 8. Legal review (before anything above touches a real customer)

*Source: `TERMS_OF_SERVICE.md`, `PRIVACY_POLICY.md`,
`compliance/DPA_TEMPLATE.md`, `compliance/DPA_ATTORNEY_SCOPE_BRIEF.md`,
`compliance/OEM_LICENSING.md`, `compliance/NO_BUDGET_TRUST_PATH.md`*

- [ ] Decide your target jurisdiction/regime (EU/UK vs. US-only vs.
      mixed) — `compliance/DPA_ATTORNEY_SCOPE_BRIEF.md`'s first question,
      needed before booking any attorney call.
- [ ] Get `TERMS_OF_SERVICE.md` attorney-reviewed before publishing or
      linking it from a signup flow.
- [ ] Get `PRIVACY_POLICY.md` attorney-reviewed before publishing.
- [ ] Get `compliance/DPA_TEMPLATE.md` attorney-reviewed before executing
      it with any real customer.
- [ ] Get a real OEM license agreement drafted before signing any
      white-label deal (see Section 2 above).
- [ ] Decide your entity structure (stay sole proprietor, or form an
      LLC/corp) — affects every legal document above, all of which
      currently assume sole proprietor. `compliance/NO_BUDGET_TRUST_PATH.md`
      Section 1 has real, low-cost options researched for this (India
      OPC via SPICe+, or a US LLC in a low-fee state) if a full-fee
      incorporation isn't in budget yet — inferred from this repo's own
      INR-denominated test fixtures that India is the likely
      jurisdiction; correct that document if it's wrong.

## 9. SOC 2 and penetration test (funding-gated — no fixed date)

*Source: `compliance/SOC2_READINESS.md`, `compliance/INTERNAL_SECURITY_REVIEW.md`,
`compliance/SOC2_ALTERNATIVE_PATH.md`, `compliance/NO_BUDGET_TRUST_PATH.md`*

- [ ] Once the hosted instance (Section 6) has run for at least a full
      quarter, engage a real CPA firm for a SOC 2 Type I report, using
      `compliance/SOC2_READINESS.md` as the intake packet. In the
      meantime, `compliance/SOC2_ALTERNATIVE_PATH.md` is the free,
      honest interim signal set (OpenSSF Scorecard, SBOM/provenance,
      and CSA STAR Level 1 — **submitted 2026-08-12, rejected the same
      day**: CSA requires an organizational-domain email, not personal
      Gmail. Blocked on Section 6's domain item above; resubmit the
      same completed CAIQ once a domain email exists — no new content
      work needed.
- [ ] Once a domain + domain email exist (Section 6), resubmit the CAIQ
      to CSA STAR under that address, then check
      `cloudsecurityalliance.org/star/registry` periodically for the
      WhitePact listing to go live, and revisit the Backup Point of
      Contact on the submission once a real second person with
      oversight authority exists (see Section 10 below).
- [ ] Operate under Type I's controls for 3-12 months, then pursue Type II.
- [ ] Commission a real third-party penetration test ($5-15K) once budget
      allows — `compliance/INTERNAL_SECURITY_REVIEW.md` narrows the gap
      but doesn't close it. `.github/workflows/security-scan.yml` (added
      this session) is the free, honest interim step: a recurring,
      automated, dated Bandit + pip-audit scan — real and checkable, but
      never describe it as a penetration test. See
      `compliance/NO_BUDGET_TRUST_PATH.md` Section 2 for exactly how to
      phrase this to a buyer without overclaiming.

## 10. Governance and organizational (founder decisions, no fixed date)

*Source: `GOVERNANCE.md`, `compliance/SOC2_READINESS.md`*

- [ ] Decide on and bring in a named second person with real oversight
      authority (advisor, fractional CISO, or eventual co-founder) — the
      single item on this whole checklist that is purely a founder
      decision, not an engineering or documentation task.
- [ ] Run `GOVERNANCE.md`'s first scheduled quarterly risk review on
      2026-10-23.
- [ ] Set a real, counsel-confirmed breach-notification timeframe once the
      DPA is attorney-reviewed (Section 8) and the internal 72-hour target
      has been tested against a real incident, not just one tabletop drill.

---

## How to use this file

Work through whichever section is cheapest or most relevant to what you're
doing right now — nothing here has a hard dependency ordering except
Section 6 (hosted instance) gating Section 9 (SOC 2) and parts of Section
7. Check items off directly in this file as you go; it's meant to be
edited over time, not a one-time snapshot.
