# WhitePact 95+ — Gap Matrix

Every real gap named in `00_REALITY_BASELINE.md`, prioritized. A gap is
only ranked P0 if it's a genuine security/release blocker found by this
audit — not because an earlier master directive happened to mention it.

## P0 — security/release blocker

| Gap | Why P0 |
|---|---|
| Independent human security review of the frozen candidate not fully closed | The exact commit reviewers should sign off on hasn't had a SHA-confirmed, security-focused human review. Everything downstream (integration, launch claims) depends on this. |
| Structural in-process execution bypass (`_dispatch_tool_unchecked()`) | Any code in-process can skip all governance. Blocks any "execution isolation" claim; must at minimum stay honestly disclosed until a real architecture decision is made. |
| Reconciliation of `main`'s independent evidence-integrity commit (`a46980d`, "fail closed on malformed evidence bundles") with PR #55's own evidence work | Two independent changes to the same subsystem (evidence handling) that have never been merged or diffed against each other — real risk of silently reintroducing a fixed bug or losing a fix during integration. |

**Checked and ruled out, not a gap:** whether PR #54 has the same CI-trigger gap this audit found and fixed on PR #55. Verified directly (`gh pr checks 54`): PR #54's base is `main` directly (not stacked on another branch), so its `pull_request` trigger always matched — all 12 checks are green. No fix needed there; the gap was specific to PR #55's stacked base.

## P1 — required for 95+ technical readiness

| Gap | Notes |
|---|---|
| Process-level execution isolation (replacing the P0 disclosure with an actual fix) | Needs the Stage 10 architecture-comparison work (separate process, Unix socket, mTLS service, etc.) before implementation — not started. |
| API-key rotation | Revoke-then-create only today; no rotation mechanism or forced-expiry. |
| Purpose binding across every live ingress path | Currently reaches some paths, not all (stdio, direct import, some ungoverned hosted-HTTP never call `resolve_authority_grant()`). |
| Concurrent `ExecutionAuthorization`/approval-consume race safety | Never load-tested under real concurrency. |
| Evidence hash-chain fork-resistance | Constraint exists (migration `0032`); never actually attacked to confirm it holds. |
| Production Docker/Helm verification | Both exist structurally; neither has been run against a live daemon/cluster in any environment available to this project so far. |
| SCIM support | Entirely missing; OIDC/SAML exist, SCIM does not — a real enterprise-IAM gap for any customer requiring automated provisioning. |
| Distributed revocation verification | The mechanism (revocation epochs) exists; multi-instance propagation under real concurrent load not verified. |

## P2 — required for high-end enterprise maturity

| Gap | Notes |
|---|---|
| Trust Center artifact (`docs/trust/ASSURANCE_MATRIX.json`) | Named in the original master directive's Stage 13, never built. Rich prose documentation exists; no machine-readable version. |
| Billing/entitlement downgrade-bypass testing | Real Stripe integration exists; adversarial testing of plan-downgrade edge cases has not been done. |
| Webhook-delivery replay protection | Outbound SSRF guard is fuzz-tested and fixed; inbound delivery replay resistance is a separate, unconfirmed property. |
| RBAC endpoint-by-endpoint exhaustive audit | The Phase 7 sweep covered org-scoping specifically, not every role/endpoint combination. |
| Observability live-fire verification | Prometheus metrics and Grafana alert rules exist; nothing has confirmed an alert actually fires end-to-end against a live deployment. |
| DR drill repeatability | One successful drill occurred; no scheduled/repeatable DR program exists yet. |
| SDK packaging | No distinct installable SDK exists separate from the library itself — worth a real decision (build one, or explicitly declare "direct library import is the SDK"). |

## P3 — useful improvement

| Gap | Notes |
|---|---|
| CLI expansion to cover governance/dispatch | Today the CLI is scoped to RAI scanning only; could be extended, not currently a blocker for anything. |
| Dashboard UX review | Functional; no dedicated usability audit performed. |
| Upstream-MCP SSRF-guard parity confirmation | Likely already shares the webhook guard's logic; worth a quick, low-effort line-by-line confirmation rather than a rebuild. |

## DEFER — not worth building now

| Item | Why deferred |
|---|---|
| Brain/AI/BCI integration | Nothing exists; building speculative interfaces before there is a concrete device/hardware partner or requirement would be pure invention, explicitly against this audit's own instruction not to invent BLE/USB/device interfaces. |
| Network-fabric/edge/device architecture | Same reasoning — no current requirement establishes what this needs to be; premature to design. |
| SOC 2 / ISO 27001 formal certification work | Explicitly named in the original directive as *not* blocking general launch, and not worth engineering time until there's budget for a real engagement (`compliance/SOC2_ALTERNATIVE_PATH.md` already states this). |
