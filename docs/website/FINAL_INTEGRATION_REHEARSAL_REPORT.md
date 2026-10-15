# WhitePact website main integration rehearsal

Date: 2026-10-07. This disposable working tree is not a final candidate,
integration approval, production qualification or merged branch.

## Exact inputs and method

- Current main snapshot: `38f927229b4ea53d19a9107c78653307f5263629`.
- Frozen qualified Phase 4: `c9622a2539f20314205e1c30a0f4b8de3927b8f4`.
- Phase 4 tree: `bf04e0022dd42d0463ec69aa0f942ff5b10c5dea`.
- Common ancestor: `cb7f479593706d841a698dafb5463f7adc744fca`.
- Computed reconciliation tree: `6b4d70ffa816f2509cc3603ba104df53416d22a8`.
- Branch: `codex/whitepact-website-integration-rehearsal`.

`git merge-tree --write-tree --name-only` returned zero conflicts. Its result
was materialized only into this previously clean disposable index/worktree.
No merge commit, branch-history merge, commit, push or reference update to main
or the qualified branch occurred. No cloud-agent script was executed.

Latest-main read-only recheck on 2026-10-07 retained the same snapshot. Reconciled website routes, environment/config interfaces, versioned docs links, workflows and lockfiles are unchanged relative to qualified Phase 4; this is no new main-side drift, not independent backend correctness proof.

## Conflict and interface inventory

| Area | Finding / evidence | Resolution |
| --- | --- | --- |
| Files | Zero textual conflicts | No manual conflict resolution |
| Deletions / renames | No new main-side deletion or rename relative to common ancestor | None |
| Website/backend interface | Reconciled dashboard/web/tests byte-identical to Phase 4 | Preserve qualified implementation; run existing web contracts |
| Dependencies | No new main-side manifest/lockfile change | Locked build preserved |
| Workflows | No main-side workflow change; reconciled workflow equals Phase 4 | No permissions or gate changes |
| Routing | Reconciled route implementation equals Phase 4 | Existing 15-route checks |
| Package/documentation | No new main-side website/package edit | Retain truthful Phase 4 identity and owner gates |
| Security/headers | No new main-side website header edit | No product/security semantics touched |
| Tests | No new main-side test conflict | Existing regression suites used unchanged |

Current main contributes exactly three files to the Phase 4 tree:
`.cursor/README.md`, `.cursor/cloud-agent-install.sh`, and
`.cursor/cloud-agent-start.sh`. They are copied from main by the reconciliation
calculation, not authored, edited or executed in this website program.

## Broader ancestry boundary

The reconciled tree differs from main in **278 files**, including 12 Python
source files inherited from earlier candidate ancestry. The website program
does not author or approve that backend ancestry. Those paths include audit
SIEM code, MFA, dashboard app/config/middleware/legacy surface, enterprise
security service and MCP server/trust-domain code. A textual merge calculation
and website tests are not a replacement for their owners' release/security
qualification. Main may move again before final integration.

## Fresh verification

- Locked frontend install, ESLint, TypeScript and production build: PASS.
- Vitest: 101 passed.
- Launch-contract tests: 11 passed; artifact audit: 15 routes PASS.
- Relevant Python website/backend tests: 71 passed, including supported local
  PostgreSQL fixtures. Three existing deprecated-variable warnings remain.
- Browser attempt 1: FAIL, heading visibility timeout at 320px. Build setup
  overlapped that attempt; it is not silently counted as passing.
- Serialized stable-artifact browser rerun: PASS; 150 axe scans and 150 responsive checks across ten widths, 15 no-JS routes, 15 asset/script-failure routes, keyboard/truth checks, reduced motion, text-scaling checks, delayed hydration, offline-after-load and clipboard-denial checks. The earlier failed overlapping attempt remains disclosed above; the rerun does not prove its cause.

The inherited manifest generator correctly regards this rehearsal as dirty;
no deployable clean-source manifest or exact-head CI claim is made for it.

## Remaining dependencies / estimated risk

- Textual conflict risk for this exact snapshot: LOW (zero conflicts).
- Website compatibility: local build/unit/web-contract evidence and the
  serialized browser rerun pass for this exact snapshot; the initial browser
  failure remains disclosed and is not counted as a pass.
- Whole-ancestry final integration risk: MODERATE/HIGH until product/security
  owners approve inherited non-website changes and combined RC validation.
- Re-fetch main and repeat this rehearsal when final integration is authorized.
- Independently review Tracks B/C/D; do not merge separate workstreams merely
  because their local checks pass.
- Owner security/legal/support/commercial/package/domain/deployment inputs and
  future TLS/edge/origin protection/post-deployment/rollback evidence stay OPEN.

PR #148 and the exact qualified Phase 4 candidate remain unchanged. No merge,
deployment, DNS, Cloudflare, Hetzner, R2, GCP, billing or production mutation.
