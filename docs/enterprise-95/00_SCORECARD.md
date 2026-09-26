# WhitePact 95+ — Scorecard

Scored independently, out of 100 each, against a "95+ enterprise
readiness" bar. Scores reflect verified/implemented evidence, not
aspiration. None of these are inflated because a component "should"
score well by category name — each score states its own evidence.

| Category | Score | Evidence | Gap to 95 | What would move it |
|---|---:|---|---|---|
| Governance | 78 | Five-way deterministic decision engine, policy/workflow engine, real tests. Mechanism is mature. | Purpose binding doesn't reach every ingress path; policy-version drift not re-checked at execute time (by design, but unverified as actually safe under adversarial conditions). | Live purpose-binding activation across all paths (P1); independent review confirming the design tradeoffs hold. |
| Security | 60 | Extensive self-verification this session (3442 tests, fuzzing found real bugs, fresh CI). One genuine, honestly-disclosed structural bypass remains open. Independent review only PARTIALLY closed (Axis 2 — the frozen candidate specifically — unconfirmed). | Structural in-process bypass; SHA-confirmed independent review; several unattacked mechanisms (evidence fork-resistance, concurrent-consume races). | Process isolation architecture + implementation; a SHA-confirmed structured independent review. |
| Execution isolation | 30 | `ExecutionAuthorization` mechanism is real and tested for the paths that reach it. No process boundary exists at all — same-process code bypasses everything. | The single largest gap in this scorecard. | Stage 10 architecture decision + real implementation (separate process/socket/service). |
| Identity | 65 | OIDC + SAML + API keys all implemented and tested. No SCIM. Root-authority/consent primitives real but reach is partial. | SCIM missing entirely; consent-check reach incomplete. | Build SCIM; complete purpose/consent live-path activation. |
| Tenant isolation | 70 | Real IDOR fix this session with an 11-test adversarial sweep, org-scoping enforced on the paths checked. | Not exhaustively audited endpoint-by-endpoint beyond the org-scoping-specific sweep. | Full RBAC/tenant gauntlet across every endpoint. |
| MCP | 75 | 11 execution paths fully mapped and documented (`ENFORCEMENT_PATH_MATRIX.md`), governance reach known precisely per path, including honest disclosure of which paths are ungoverned by design (stdio). | stdio is intentionally open by design under non-enterprise mode — a real, disclosed, not-yet-closed-for-every-config gap. | Nothing new needed technically; mostly a documentation/deployment-guidance completeness question at this point. |
| Networking | 40 | Networking = the MCP transport layer; no separate network-fabric/edge layer exists. | No dedicated network-fabric architecture; not clear one is actually needed yet. | Depends entirely on a real future requirement — premature to build now (see Gap Matrix, DEFER). |
| Brain/AI integration | 0 | Nothing exists. Not partially built — zero implementation. | Everything. | A real requirement/partner would need to exist first; nothing to "move" without one. |
| Evidence | 55 | Hash-chain + fork-prevention constraint exist. Never attacked to confirm it holds. `main`'s independent evidence-bundle fail-closed work unreconciled with PR #55's. | Fork-resistance unattacked; unreconciled parallel work; `revocation_epoch` not bound at grant time. | Attack the fork-prevention constraint directly; reconcile the two evidence-handling implementations during integration. |
| Reliability | 55 | Real DR drill performed once; backup script exists; no repeatable/scheduled DR program. | One-time proof, not an operational program. | A second, independently-scheduled DR drill; documented cadence. |
| Deployment | 50 | Dockerfile + Helm chart both structurally complete and pinned/hardened. Neither smoke-tested live. | No live verification anywhere — this environment has no Docker daemon or cluster access. | A live smoke test against a real container/cluster (external dependency — needs infrastructure this project doesn't currently have). |
| SRE | 40 | Prometheus metrics + Grafana alert rules exist. No live-fire confirmation an alert actually pages anyone. | Entirely unverified in a live setting. | A real deployment with real alert-routing to confirm the pipeline works end-to-end. |
| Database | 85 | PostgreSQL migration round-trip verified for real this session (37/37, both directions), no schema conflicts with `main`. Strongest category in this scorecard. | Concurrent-write race safety under real load not tested. | Load-test concurrent writes against the real schema. |
| Privacy | 60 | `PrivacyLabel` (federated learning, differential privacy) implemented; privacy policy docs exist and are honest about scope. | Not independently re-verified this session; differential-privacy math not re-audited. | An independent review of the DP implementation specifically. |
| Supply chain | 80 | Real, and only on `main`: SLSA Build L3, reproducible builds, signed tags, Scorecard hardening, three real verified releases. | This work needs to reach PR #55's branch via integration before it benefits the Heart/governance work too. | Complete the integration recommended in `00_INTEGRATION_STRATEGY.md`. |
| Developer experience | 45 | CLI exists but scoped narrowly (RAI scanning only); no distinct SDK package. | No governance-facing CLI/SDK surface at all — a developer wanting to script against the governance API has only the REST API/direct import. | A deliberate SDK-vs-direct-import decision, then build accordingly. |
| Dashboard | 55 | Functional SPA with billing UI exists. No dedicated UX review performed as part of any session's work. | Unknown — not assessed, not just "gap known and unaddressed." | A real UX audit. |
| Trust Center | 15 | Rich prose security documentation exists. The specific machine-readable artifact (`docs/trust/ASSURANCE_MATRIX.json`) does not exist at all. | Almost everything about a "Trust Center" as a distinct, structured artifact. | Build it — this is a well-scoped, low-effort win relative to most other gaps here. |
| Enterprise IAM | 55 | OIDC + SAML real and tested. SCIM entirely missing. | SCIM. | Build SCIM. |
| Commercial controls | 60 | Real Stripe integration, plan-gating, billing UI. Downgrade/entitlement-bypass paths untested. | Adversarial testing of the billing boundary. | A dedicated billing/entitlement attack pass. |
| Procurement readiness | 35 | OpenSSF Best Practices + Baseline self-certifications real; no SOC 2/ISO, explicitly and correctly deferred rather than faked. No Trust Center artifact for a procurement team to point to. | Depends heavily on the Trust Center gap and on the independent-review gate fully closing. | Trust Center + a SHA-confirmed independent review together would move this the most. |

## Overall

**Not a single blended number** — the whole point of scoring these
independently is that a blended average would hide the execution-
isolation and Brain/AI-integration zeros behind the database category's
85. Read the table, not a summary statistic, for any real decision.

If a single approximate figure is wanted anyway for rough calibration:
unweighted mean across the 21 categories above is **~53/100**. This is
explicitly *not* the same claim as "53% enterprise ready" — it is an
arithmetic average of 21 differently-important categories, offered only
because a number was requested, with this caveat attached every time it
is quoted.
