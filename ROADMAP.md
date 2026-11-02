# Roadmap

**Canonical roadmap.** This is the one place to answer "what is WhitePact
building, and in what order" — synthesized from `VERSION_ROADMAP.md` (the
detailed, version-numbered technical plan) into the NOW / NEXT / LATER
structure OpenSSF's Silver guidance asks for. `VERSION_ROADMAP.md` has the
full detail per version (through v6.0.0); this document is the short,
current-truth summary that links to it rather than duplicating it.

Two other documents cover adjacent, non-contradictory ground and are kept
deliberately separate rather than merged in:
- **`STRATEGY_ROADMAP.md`** — the same plan from the business/revenue side (its four phases map roughly onto v2–v5 below). Context and rationale, not a second source of what ships when.
- **`GAME_CHANGER_STRATEGY.md`** / **`GAME_CHANGER_BUILD_PLAN.md`** — a specific strategic bet (infrastructure-first: free public trust registry, agent-native trust-check primitive) explored as an alternative framing of the v4.0.0 "public trust registry" work below, not a competing roadmap.

**A known limitation of this synthesis, stated honestly rather than hidden**: `VERSION_ROADMAP.md` was last reviewed 2026-07-23. Real work has shipped since then (see `CHANGELOG.md` and `MIGRATION_WHITEPACT_V2.md`, both more frequently updated) that isn't yet reflected in `VERSION_ROADMAP.md`'s per-version checklists. Treat `CHANGELOG.md` as the ground truth for "what has actually shipped" and this document plus `VERSION_ROADMAP.md` as the plan for what's next — a stale plan is a real, tracked gap (see Exit Criteria below), not silently ignored.

---

## NOW — shipped, v1.2.3

Public Leaderboard, Trust Index/Passports + embeddable badges, AI Incident
Database, TOTP MFA, expanded field encryption, DB-persisted webhooks, full
dashboard UI rebuild, white-label branding, a live hosted instance at
[whitepact.com](https://whitepact.com), the WhitePact v3 machine-authority
layer (Execution Permits, revocation, multi-approver quorum, delegation
chains, hash-chained evidence, upstream MCP tool discovery/trust scanner),
OpenSSF Best Practices Passing + OSPS Baseline Level 1. Full detail:
`CHANGELOG.md`.

## NEXT — v2.0.0, "Real hosted tier, sellable" (target: Months 1–3 from v1.2.0)

**Will build**:
- Stripe billing verified end-to-end with a real test purchase, not just unit tests
- Persistent storage proven under real concurrent multi-user load, not just "survived a redeploy"
- MCP directory submissions actually completed (drafted in `compliance/MCP_DISTRIBUTION_GUIDE.md`)
- 3–5 design partners onboarded on a free enterprise trial in exchange for case studies
- First 1–3 real paying customers

**Already done, ahead of schedule** (see `VERSION_ROADMAP.md` for dates): custom domain + TLS, self-serve `/signup` onboarding wizard.

**Will not build yet**: SOC 2, an independent pentest, consumer-facing product surface, new AI-safety features. Same discipline as `STRATEGY_ROADMAP.md`'s Phase 1 — this version is about revenue and removing the founder as a sales bottleneck, not new capability.

**Dependency**: none blocking — in progress now.

**Exit criteria**: 1–3 paying customers, even at a discounted founding-customer rate. v3.0.0 does not start on hope if this isn't hit.

## LATER — v3.0.0 through v6.0.0

Full detail in `VERSION_ROADMAP.md`. Summary:

- **v3.0.0 — "Enterprise trust"** (Months 4–8 from v2.0.0): SOC 2 groundwork, deeper enterprise integrations, hardened multi-tenant guarantees.
- **v4.0.0 — "Public trust registry"** (Months 9–15 from v3.0.0): the free public trust-check infrastructure bet — see `GAME_CHANGER_STRATEGY.md`.
- **v5.0.0 — "Platform and ecosystem"** (Months 16+ from v4.0.0): third-party integrations, ecosystem partnerships.
- **v6.0.0 — "Category-defining standard"** (directional, no committed date): aspirational, explicitly not committed to.

**Will not build**: anything in v4.0.0 onward starts only once its predecessor's revenue/proof target is hit, or there's an explicit, reasoned decision to proceed without it — no version begins on a calendar date alone. v4.0.0 onward is directional, not committed, exactly as `VERSION_ROADMAP.md` states for itself.

**Dependencies**: v3.0.0 depends on v2.0.0's revenue gate; v4.0.0+ depend on their respective predecessors' stated gates.

---

## Deferred, not abandoned

- **Second maintainer / bus factor ≥ 2** — real, structural gap tracked in `compliance/OPENSSF_SILVER_GAP_ANALYSIS.md`. Not a feature to build; a real person who doesn't exist yet.
- **Accessibility and internationalization infrastructure** — in progress as of this document's writing (2026-08-18), tracked as their own build items, not folded into a version number above since they're compliance/quality work rather than product features.
- **Docker image publishing on tag** — `RELEASING.md` states plainly this doesn't exist yet; a deployer builds the image themselves from tagged source today.

---

*Last synthesized: 2026-08-18. Update this document the same day a version target changes, per the same discipline `GOVERNANCE.md` holds itself to.*
