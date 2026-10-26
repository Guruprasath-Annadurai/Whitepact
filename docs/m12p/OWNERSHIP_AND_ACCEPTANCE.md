# M12-P scope, ownership and acceptance boundary

Baseline: b08362a541bc0b3a9eaae34aab4691fab65934f8,
tree5803bb4b83f759670f9c0828befa2e245a5b8653. PR204 is preserved.
Worktree /Users/ag/whitepact-m12p-product-excellence, branch
codex/whitepact-m12p-product-excellence. No M13 entry or production release.

| Owner | Exclusive changed surface |
|---|---|
| Codex developer DX | scripts/developer/first_run.py, examples/developer/m12p_governance_probe.py, tests/test_m12p_developer_*.py, docs/developer/M12P_LOCAL_FIRST_RUN.md |
| Codex dashboard reads | CanonicalPanels.tsx, m12p-dashboard-reads tests, production-unwired inventory component/tests |
| Codex coordinator | frontend api.ts resilience/tests, browser acceptance and redacted diagnostics, product-only CI, generated frontend distribution, M12-P reports/ADRs/runbook |
| Antigravity M12-SR — untouched | Authority/root/consent, signing, delegation/revocation, execution admission/isolation/egress, security repositories and reviewed contract decisions |

Requirements → evidence:

- Offline diagnostic → fixed vocabulary/no secrets/no writes/no connections;
  URL/alias/config/prerequisite negative tests. PASS is configuration only.
- Bounded read → 15-second GET/HEAD deadline, caller cancellation, explicit
  retry, malformed JSON errors; no automatic mutation retries or authority cache.
- Current approval read → repeated IDs fetched once per current snapshot,
  obsolete requests aborted/ignored, stale confirmations unavailable. Server
  authorization remains required regardless of browser display.
- UI preparation → exact reader-derived types, explicit unavailable/error/empty
  states, unknown lifecycle retained; no production route or mutation API.
- Actual browser → migrated isolated PostgreSQL plus actual running application
  for public navigation/unauthenticated console refusal. No root/identity seeds.
  Requires installed Chromium and explicit PLAYWRIGHT_BROWSERS_PATH because
  pytest deliberately isolates HOME. Separate fixture browser tests exercise
  authenticated UX and uncertainty, NOT customer authority qualification.
- Review candidate → frozen commit/tree, clean tracked tree, normal draft PR and
  exact-head job evidence. No acceptance inferred from a predecessor's CI.

M12-C security dependencies remain blocked. The legacy seeded development
customer-journey script is not promoted to a real root/consent journey; credential
diagnostic logging was narrowed without modifying its authority seeder.
No production credentials, root fixtures or local signing secrets introduced.

GLOBAL PRODUCTION NO-GO. No main merge, package publication, spending/apply,
deployment, cloud/DNS mutation, directory campaign, rebase or force push.
