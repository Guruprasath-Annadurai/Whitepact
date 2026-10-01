# WhitePact 95+ — Phase 0 Reality Baseline

**Audit only. No code implemented, no features created, no PR merged, no
change to the frozen security candidate.** Every claim below is grounded
in a `git`/`gh` command actually run against the live repository during
this pass, not carried forward from prior status reports.

## Identity of everything inspected

| Ref | SHA |
|---|---|
| `origin/main` | `8f8ef53f0460c99115f5656dfa4d31775bca4d6a` |
| PR #54 head (`security/enterprise-neural-remediation`) | `32eb2a6b1891fa751376bc8dbee8bd048256efb3` |
| PR #55 head (`security/heart-production-closure`) | `22b2c77543551057031e73e986c332c19243c57e` |
| PR #50 head (`security/enterprise-neural-phase-0-1`) | `9d1fdad2dbaeea1fd3d12aeea12bc13b9917a1fc` |
| Common merge-base (all three PRs vs `main`) | `9dcdc1bebe0ad856bd399dc627d17c35a2cc5828` |
| Frozen security-review candidate (unchanged by this audit) | `7df5bfb40cbb14543267f506cf18215b8f3395f0` |

PR #55 is 0 commits behind, 40 ahead of PR #54's own branch tip (fully
contains it, stacked directly on top). All three PRs share the same
merge-base with `main`. `main` has moved 82 commits' worth of diff
(measured in file-diff terms; 12 actual merge commits) ahead of that
merge-base independently of any of these branches — see
`00_INTEGRATION_STRATEGY.md` for what those 12 commits actually contain.

**"Brain/AI/neural" naming clarification (a real finding, not
assumed):** `docs/enterprise-neural/` and branch name
`security/enterprise-neural-remediation` are the codename of PR #54's
**security remediation initiative** (18 phases of security hardening),
not a biological/BCI/neural-hardware feature. Grep across both `main`
and PR #55 for `brain|neural|bci|device_identity|attestation` finds:
`governance/attestation.py` (identity attestation in the governance
sense — root authority, consent proofs — unrelated to neuroscience or
hardware), and the `enterprise-neural` docs directory itself. **There is
no Brain-Computer-Interface, neural-hardware, or biological-neural
implementation anywhere in this repository.** Items 25 and part of 4/24
below are classified `MISSING` on that basis — nothing exists to audit,
not a gap in this audit's thoroughness.

---

## Capability classification (25 areas)

Legend: VERIFIED (independently re-confirmed working this session) ·
IMPLEMENTED (code exists, not independently re-verified in this pass) ·
PARTIAL (real but incomplete) · MISSING (no implementation found) ·
BLOCKED (implementation exists, verification blocked by infrastructure)
· EXTERNAL_DEPENDENCY (requires a third party) · NOT_APPLICABLE

### 1. Current `origin/main`
**VERIFIED.** `8f8ef53f0460c99115f5656dfa4d31775bca4d6a`. 12 commits
ahead of the shared merge-base: 3 release-engineering commits (v1.2.4,
v1.2.5, v1.2.6), SLSA Build L3 / reproducible-build hardening, OpenSSF
Scorecard hardening, a "complete enterprise trust and assurance
hardening" commit (evidence-bundle fail-closed handling, CAIQ mapping,
public-trust-claim-boundary policy — authored by a different
contributor, "Techezz Infos"), pa11y accessibility tooling replacement,
MCP distribution/Anthropic-connector submission docs. **None of PR #54
or PR #55's Heart/governance work is present on `main`.**

### 2. PR #54 cumulative security work
**IMPLEMENTED, not independently re-verified in this pass beyond what
this session's own predecessor work already covered.** 18-phase
"Enterprise Neural Remediation" initiative (`docs/enterprise-neural/`,
51 files, 0 of them present on `main`). Covers crypto activation,
consent/root-authority primitives, and multiple design/report pairs per
phase.

### 3. PR #55 cumulative Heart/security-hardening work
**VERIFIED** (this session's own direct work): Heart Production Closure
Gaps A–D, Enforcement Chokepoint Closure E0–E6, 17 enterprise-readiness
gaps, two pre-existing test-infra bugs fixed, a full security-freeze
process (Stages 0–5), CI-gap fix, `auth_enabled`/DB-URL-fallback fixes,
external-review documentation. Full detail: `docs/security-review/` and
`docs/heart-production-closure/` on the PR #55 branch (not duplicated
here).

### 4. Current Brain/AI/neural implementation
**MISSING**, per the naming clarification above. No neural/BCI
implementation exists. `NOT_APPLICABLE` for anything beyond the
governance-sense "attestation" primitive.

### 5. Current MCP/networking implementation
**IMPLEMENTED.** `src/responsibleai/mcp/` — stdio transport, Streamable
HTTP, HTTP+SSE (legacy), upstream MCP proxy/gateway. Fully documented in
`ENFORCEMENT_PATH_MATRIX.md` (11 execution paths, governance-reach
mapped per path). This *is* the "networking" layer of this codebase
today — there is no separate lower-level network-fabric/device/edge
layer (see item 24).

### 6. Deployment/container/Helm state
**PARTIAL.** Dockerfile with pinned digest + hardening flags
(`read_only`, `cap_drop: [ALL]`, `no-new-privileges`) exists on PR #55;
`helm/rai-governance/` chart exists on `main` with HPA, PDB, ingress,
service account, ConfigMap/Secret templates — structurally complete.
**Neither has been smoke-tested against a live cluster or a live Docker
daemon in this environment** (no Docker daemon available). `helm lint`
runs in CI (`Helm chart lint` job, currently green) but that is static
validation, not a live deployment rehearsal.

### 7. Authentication/RBAC/tenant isolation
**VERIFIED** (this session): Bearer API key / OIDC JWT / VC-JWT auth;
`Role` enum (VIEWER/ANALYST/ADMIN/OWNER) enforced via FastAPI
dependencies; Phase 7 cross-tenant IDOR fix with an 11-test adversarial
sweep. **PARTIAL** beyond that: full RBAC endpoint-by-endpoint audit
(every ADMIN-only route actually rejecting ANALYST tokens) not
exhaustively re-verified — named as an open item in
`STAGE5_INDEPENDENT_REVIEW_GATE.md`.

### 8. API-key lifecycle
**PARTIAL.** Create/revoke exist and are ownership-checked (Phase 7).
**No rotation mechanism** — revoke-then-create is the only path. No
scheduled/enforced expiry found.

### 9. Purpose/consent live paths
**PARTIAL.** `resolve_authority_grant()` validates purpose against
`ConsentProof` scope where reached; per
`ENFORCEMENT_PATH_MATRIX.md`, several paths (stdio, direct import,
ungoverned hosted-HTTP) never reach this check at all — not a defect in
the mechanism, a gap in its *reach*. Live-path activation across every
ingress (Stage 7 of the original master directive) has not been done.

### 10. `ExecutionAuthorization` and execution boundaries
**VERIFIED** for the mechanism (single-use, TTL-bound,
digest-bound-to-action including `purpose`). **The one honestly-open
structural gap**: `_dispatch_tool_unchecked()` is directly importable by
any code in the same process, bypassing all governance —
`EXECUTION_PROCESS_BOUNDARY_STATEMENT.md`. Concurrent-consume race
safety **not independently verified** (`BLOCKED` on load-testing
infrastructure/time, not attempted).

### 11. Replay/revocation
**VERIFIED** for grant-time and resume-time checks (this session's
predecessor work fixed the approval-resume TOCTOU). **PARTIAL**:
`revocation_epoch` is never populated on `ExecutionAuthorization` at
grant time (named gap); distributed/multi-instance revocation
propagation beyond the DB-backed epoch table not independently
load-tested.

### 12. Approval system
**IMPLEMENTED**, quorum support exists (`governance_approval_votes`,
migration `0018`). Resume-time re-check verified this session.

### 13. Evidence/audit integrity
**PARTIAL.** Hash-chain + fork-prevention constraint (migration `0032`)
exist; **fork-resistance never actually attacked** in this session's own
verification (named open item). Main's independent
"fail closed on malformed evidence bundles" commit (`a46980d`) is not
present on PR #55 and has not been reconciled with PR #55's own evidence
work — a real integration item, not yet assessed for conflict.

### 14. PostgreSQL/migrations
**VERIFIED.** All 37 migrations on PR #55 round-tripped against real
PostgreSQL 17 this session (up and down). Migration divergence from
`main` (which has 29) is **purely additive and non-conflicting**: `main`
has made zero schema changes since the merge-base; migrations
0001–0029 differ from PR #55's copies only in formatting (whitespace/
column alignment from a `ruff format` pass), not schema; PR #55 adds
0030–0037 cleanly on top.

### 15. Webhooks
**VERIFIED.** SSRF guard (`validate_webhook_url()`) fuzz-tested this
session (2 real crash bugs found and fixed: malformed IPv6, oversized
hostname/IDNA). **PARTIAL**: inbound webhook-delivery replay protection
not independently verified; whether upstream-MCP-server URLs share the
same guard not confirmed line-by-line.

### 16. Billing/entitlements
**IMPLEMENTED**, not independently re-verified this session. Real Stripe
integration (`billing/stripe_service.py`), plan-gating
(`require_plan()`), Stripe fields on `organizations` (migration `0003`).
Plan-downgrade/entitlement-bypass scenarios **not tested** (named gap).

### 17. Enterprise IAM
**PARTIAL.** OIDC (JWKS-validated) and SAML both implemented with tests
(`auth/oidc.py`, `auth/saml.py`, `tests/test_oidc*.py`,
`tests/test_saml*.py`). **SCIM: MISSING** — no SCIM module, endpoint, or
test found anywhere in the repository (`main` or PR #55).

### 18. Observability/SRE
**PARTIAL.** Prometheus metrics (`dashboard/prometheus.py`, this
session added 6 new governance-specific metrics), Grafana provisioning
+ alert rules exist (`grafana/`). No independent verification that
alerting actually fires against a live deployment (no live environment
available); no incident/on-call runbook beyond
`docs/operations/INCIDENT_RESPONSE.md` (exists, not live-drilled beyond
its own documentation).

### 19. DR/backups
**PARTIAL.** `scripts/backup-postgres.sh` exists;
`docs/operations/DR_RESTORE_DRILL.md` documents a real (not simulated)
`pg_dump`/drop/recreate/restore cycle performed once, earlier this
session's predecessor work. One successful drill is evidence of the
mechanism working, not of a repeatable, scheduled DR program.

### 20. Dashboard/product UX
**IMPLEMENTED**, not independently re-verified this session (static SPA
under `dashboard/static/`, `billing.html` present). No UX/usability
review performed as part of this audit.

### 21. Trust Center/security documentation
**PARTIAL, split.** Extensive honest security *documentation* exists
(`SECURITY_ASSURANCE_CASE.md`, `THREAT_MODEL.md`,
`ENTERPRISE_SECURITY.md`, `docs/security-review/` on PR #55, `docs/
enterprise/`). **A dedicated, machine-readable "Trust Center" artifact
(`docs/trust/ASSURANCE_MATRIX.json`, named in the original master
directive's Stage 13) does not exist on either branch** — `MISSING`.

### 22. SDK/CLI/developer experience
**PARTIAL.** No separate installable SDK package found distinct from
importing `responsibleai`/`biasbuster` directly — the README's "Python
SDK" section documents direct library usage, not a distinct SDK
artifact. CLI exists (`biasbuster.cli:main`) but, per
`ENFORCEMENT_PATH_MATRIX.md` Path 9, is scoped to RAI scanning/
benchmarking only — it does not touch governance/dispatch at all.

### 23. Supply-chain/release engineering
**VERIFIED, and only on `main`, not on PR #55.** `main` has real,
independently-landed SLSA Build L3 evidence, reproducible builds, signed
version tags, OpenSSF Scorecard hardening (v1.2.4–v1.2.6 releases). PR
#55 does not have any of this — it branched before these landed. This is
a genuine asset the integration strategy must preserve, not overwrite.

### 24. Networking/device/edge architecture
**MISSING.** No dedicated network-fabric, device-identity, or edge layer
exists beyond the MCP transports covered in item 5. Nothing to audit
beyond what's already described there.

### 25. BCI integration contracts
**MISSING / NOT_APPLICABLE.** Per the naming clarification at the top of
this document: no BCI (brain-computer interface) work exists anywhere in
this repository. This is not a partially-built feature; it does not
exist. Any future BCI work would start from zero, with no current
contracts, interfaces, or even placeholder modules to build on.
