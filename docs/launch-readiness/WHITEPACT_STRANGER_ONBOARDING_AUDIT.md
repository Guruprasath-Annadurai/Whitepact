# WhitePact stranger onboarding audit (Cell A)

**Audit date:** 2026-09-26  
**Baseline:** `origin/main` @ `a29d9be650b1ca0937df766774fc220412588d0a` (tree `ec239934fdebe6d5f4ec201231ecde8b428ca945`)  
**Scope:** Documentation, install paths, MCP, API examples — **no Formula** (`src/responsibleai/formula/` untouched)

## First entry point

| Entry | Observed role |
|-------|----------------|
| `README.md` | Primary GitHub/PyPI landing; install + **30-second quickstart** |
| PyPI `rai-governance-platform` | Same README content for package consumers |
| `server.json` / MCP Registry | MCP distribution metadata |
| `docs/integrations/README.md` | MCP client matrix |

**Finding:** README quickstart optimizes for **trust score** (`POST /api/evaluate`), not the
full **authority allow → deny → evidence → revoke** chain a security evaluator expects.

## Steps to first success (before Cell A fixes)

| Persona | Steps (approx.) | First “success” |
|---------|-----------------|-----------------|
| README follower | install → uvicorn → curl `/api/evaluate` | Trust score JSON |
| Governance engineer | discover `examples/08_*` or tests | In-process gateway demo |
| MCP integrator | read integrations README → configure client | Tool list / health tool |
| Docker user | `.env` + `docker compose up` | `/api/health` |

**Gap:** No single canonical doc linked from README for **stranger authority path** (P1 onboarding).

## Hidden assumptions

- Familiarity with `responsibleai` import name vs WhitePact branding (`docs/PACKAGE_IDENTITY.md` exists but easy to miss).
- Org-scoped API keys for `/api/governance/*`; legacy flat keys rejected (400).
- `RAI_AUTH_ENABLED=true` by default — curl examples without Bearer fail on protected routes.
- MCP HTTP requires allowed origins and bearer token for hosted endpoint.
- Phase 1 authority (root/consent/delegation) is exercised heavily in tests, lightly in README.
- Sovereign / Formula / phase7a docs intermixed under `docs/` — strangers may enter wrong subtree.

## Dependencies

- Python 3.11+; optional Postgres, Redis, OTEL per extras.
- Docker build compiles web UI (Node stage) — heavier than pip editable.
- Helm assumes Kubernetes operator knowledge; values in `helm/rai-governance/values.yaml`.

## Environment variables

- Canonical list: `.env.example` (RAI_* and WHITEPACT_*).
- Production field encryption required when `WHITEPACT_ENV=production`.
- **Gap addressed:** installation + troubleshooting docs cross-link `.env.example`.

## Stale or contradictory instructions

| Item | Note |
|------|------|
| README “30-second quickstart” vs authority story | Complementary, not contradictory — needs explicit pointer |
| Multiple quickstart-like files | `examples/01_*` … `08_*` without ordered “start here” until Cell A `docs/START_HERE.md` |
| `main` worktree drift | Local clones may be behind `origin/main`; strangers should `git pull --ff-only` |

## Broken links

- Not exhaustively link-checked in this audit run (no `lychee` job executed here).
- Internal doc links in new Cell A docs use relative paths under `docs/`.

## Founder-knowledge traps

- Creating org-scoped API keys via dashboard UI.
- Choosing between stdio MCP vs hosted HTTP + bearer.
- Knowing that `examples/08_whitepact_enterprise_scenario.py` is the real governance tour.
- Paddle/billing paths in README — not required for governance quickstart.

## Unnecessary complexity for strangers

- Large `docs/superpowers/` and `docs/formula/` archives visible in tree listing.
- README feature table is broad — authority layer buried mid-document.

## Stuck points (risk)

| Risk | Severity | Mitigation in Cell A |
|------|----------|-------------------|
| Auth enabled, no key | P2 | quickstart + troubleshooting |
| Governance 400 without org key | P1 | http_governance.md |
| Expect revoke in README quickstart | P1 | `quickstart_stranger_authority.py` + `docs/quickstart.md` |
| Docker without `.env` | P2 | installation.md |

## Artifacts added (Cell A)

- `docs/START_HERE.md`, `docs/quickstart.md`, `docs/installation.md`, `docs/mcp-quickstart.md`, `docs/troubleshooting.md`
- `docs/examples/http_governance.md`
- `examples/quickstart_stranger_authority.py`
- `scripts/launch-readiness/clean_room_smoke.sh`

## Remaining gaps (honest)

- Automated link checker not added to CI in this cell.
- Full HTTP quickstart with org bootstrap UI flow not scripted (requires dashboard signup).
- Hosted MCP endpoint depends on third-party availability for `integration_smoke.py`.
