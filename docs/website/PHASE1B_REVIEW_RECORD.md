# Phase 1B website review record

Base: `52d9b3c5497af24bb7d4a7147e33deaadc64296e`.
Branch: `codex/whitepact-global-website-phase1`.
Date: 2026-10-04. Owner-review prepared; not owner-approved and not deployed.

## Review method and scope

All source deltas and added source files were reviewed against the base; generated HTML was exercised through public delivery tests and the 15-route browser matrix. All 23 generated JavaScript chunks passed Node module syntax checks, and generated HTML asset references resolved. Hashed chunk replacement follows the Vite module graph; removals of redundant WOFF assets retain equivalent WOFF2 font families/weights. No source file outside the inventory was changed.

The two Python modules change public HTML selection, llms discovery, 404 HTML and public CSP path classification only. AuthPages changes field-error accessibility only. SovereignPage changes shared corporate navigation/main landmark only. CI adds the website matrix to the existing frontend job, with no permission or test weakening. Existing product modules, SDKs, migrations, database schema, runtime decisions, grants, approvals/revocation, MCP trust, workers and billing entitlement code are unchanged from the required base. Existing tests continue to exercise authentication and backend truth.

## Corrections found during review

- Public evidence-detail guidance named a nonexistent SDK route. Corrected to supported bearer listing versus session-authenticated detail, with an explicit baseline SDK mismatch warning. SDK/backend remediation is outside website scope.
- Published PyPI distribution exists but current published version was 1.2.6 on 2026-10-04, behind the 1.3.1 source candidate. Local V1 setup now pins the reviewed source baseline; published install is not misrepresented as this candidate.
- Trust cards now carry scope/status/pinned source/limitations, not universal check marks or completed certification.
- Companion commercial/legacy/IA documents no longer describe historical wording as current implementation. Commercial/contact/legal decisions remain open.
- Scheduled mobile-menu focus is canceled on close, preventing late focus movement after Escape.
- New delivery test formatting and generated private/404 trailing whitespace corrected without changing security semantics.

## Reviewed claims

Accepted with qualifications: independent pre-execution authority on supported configured paths; identity/intent/billing are not authority; conceptual control chain; UNKNOWN requires reconciliation; revocation cannot undo completed external effects; hash-chain evidence has verifier/storage boundaries.
Revised: evidence API guidance, source versus published distribution, Trust evidence mapping, legacy/current source descriptions.
Gated: paid hosted offers, deployed Paddle provider, production availability, legal approval, contact identity, independent testing/certification and universal non-bypassability.
Owner action records: `COMMERCIAL_SOURCE_OF_TRUTH_GAPS.md`. Production identity remains `P0 — OPEN EXTERNAL/DEPLOYMENT GATE`.

## Publication and exact-head evidence sequence

Commit the reviewed source/build/tests/documents once after final local validation. Push only this website branch and open a draft PR; do not merge. The required base includes 76 inherited commits above current main, which must be disclosed separately from this website delta. No inherited commit is rewritten.

Capture CI IDs, head SHA and individual jobs after publication. A PR merge-test ref may differ from its head: record both rather than asserting they are identical. Final CI/evidence report is a separate, uncommitted owner-review artifact at `docs/website/PHASE1_EXACT_HEAD_CI_EVIDENCE.md` and the Phase 1B final report. These records must not create a new untested engineering SHA. Evidence is not a claim of green CI until completed runs actually prove it.

No production deployment, DNS/proxy/cloud mutation, production billing operation, release, tag or main merge is authorized here. Readiness remains 72% repository candidate / 54% global under the existing editorial rubric, not certification or coverage.

## Categorized complete inventory

Status letters are Git's staged inventory at review time. Generated asset renames include old and new paths. This review record itself is an additional documentation file.

### Website UI / content

- `M` `web/src/App.tsx`
- `A` `web/src/components/CorporateNav.tsx`
- `M` `web/src/content/commerce.json`
- `A` `web/src/content/control-chain.ts`
- `A` `web/src/content/corporate.json`
- `A` `web/src/content/public-info.json`
- `A` `web/src/corporate.css`
- `M` `web/src/features/auth/AuthPages.tsx`
- `A` `web/src/features/marketing/CorporatePages.tsx`
- `M` `web/src/features/marketing/HomePage.tsx`
- `M` `web/src/features/marketing/PublicPages.tsx`
- `M` `web/src/features/sovereign/SovereignPage.tsx`
- `A` `web/src/fonts.css`
- `M` `web/src/main.tsx`
- `M` `web/src/test/account-flows.test.tsx`
- `A` `web/src/test/corporate-site.test.tsx`
- `M` `web/src/test/public-site.test.tsx`
- `M` `web/tsconfig.node.json`

### Public delivery / generated artifacts

- `M` `src/responsibleai/dashboard/app.py`
- `M` `src/responsibleai/dashboard/middleware.py`
- `R085` `src/responsibleai/dashboard/static/whitepact/assets/ApiKeysPage-DCbbE6AM.js → src/responsibleai/dashboard/static/whitepact/assets/ApiKeysPage-Bman8ECx.js`
- `A` `src/responsibleai/dashboard/static/whitepact/assets/AuthPages-CYIlgjHU.js`
- `D` `src/responsibleai/dashboard/static/whitepact/assets/AuthPages-D8l-55ID.js`
- `A` `src/responsibleai/dashboard/static/whitepact/assets/CorporatePages-DUxlPcPw.js`
- `R069` `src/responsibleai/dashboard/static/whitepact/assets/DashboardShell-YUiB0XLF.js → src/responsibleai/dashboard/static/whitepact/assets/DashboardShell-CsnYe0hE.js`
- `A` `src/responsibleai/dashboard/static/whitepact/assets/DomainPage-Bky2s829.js`
- `D` `src/responsibleai/dashboard/static/whitepact/assets/DomainPage-uzNSJYtC.js`
- `R091` `src/responsibleai/dashboard/static/whitepact/assets/OnboardingPage-RuOY5Jpy.js → src/responsibleai/dashboard/static/whitepact/assets/OnboardingPage-CH77mZua.js`
- `R088` `src/responsibleai/dashboard/static/whitepact/assets/OverviewPage-BHVZzmlQ.js → src/responsibleai/dashboard/static/whitepact/assets/OverviewPage-4rbvZEqF.js`
- `R096` `src/responsibleai/dashboard/static/whitepact/assets/PolicyPage-B8QlydXh.js → src/responsibleai/dashboard/static/whitepact/assets/PolicyPage-CiImYT0-.js`
- `R051` `src/responsibleai/dashboard/static/whitepact/assets/SovereignPage-CVrKQN5r.js → src/responsibleai/dashboard/static/whitepact/assets/SovereignPage-iK7GbY9g.js`
- `D` `src/responsibleai/dashboard/static/whitepact/assets/SovereignWorkbench-G_85xrz5.js`
- `A` `src/responsibleai/dashboard/static/whitepact/assets/SovereignWorkbench-l7S48S0L.js`
- `R074` `src/responsibleai/dashboard/static/whitepact/assets/TrustCore-BXp2rRKx.js → src/responsibleai/dashboard/static/whitepact/assets/TrustCore-BVhKRK99.js`
- `R082` `src/responsibleai/dashboard/static/whitepact/assets/building-2-CAZGSzCM.js → src/responsibleai/dashboard/static/whitepact/assets/building-2-BG0utDr1.js`
- `R072` `src/responsibleai/dashboard/static/whitepact/assets/circle-question-mark-BIWuElON.js → src/responsibleai/dashboard/static/whitepact/assets/circle-question-mark-CqTFuw4-.js`
- `R073` `src/responsibleai/dashboard/static/whitepact/assets/eye-B-5LhA3L.js → src/responsibleai/dashboard/static/whitepact/assets/eye-efRYTb-0.js`
- `D` `src/responsibleai/dashboard/static/whitepact/assets/ibm-plex-mono-latin-400-normal-CvHOgSBP.woff`
- `D` `src/responsibleai/dashboard/static/whitepact/assets/ibm-plex-mono-latin-500-normal-CB9ihrfo.woff`
- `A` `src/responsibleai/dashboard/static/whitepact/assets/index-5mevyJ4C.js`
- `A` `src/responsibleai/dashboard/static/whitepact/assets/index-BL1PdgcR.css`
- `D` `src/responsibleai/dashboard/static/whitepact/assets/index-CERQdcHW.js`
- `D` `src/responsibleai/dashboard/static/whitepact/assets/index-Co1xVfto.css`
- `R081` `src/responsibleai/dashboard/static/whitepact/assets/key-round-DQsFwv30.js → src/responsibleai/dashboard/static/whitepact/assets/key-round-4_kibbIn.js`
- `D` `src/responsibleai/dashboard/static/whitepact/assets/manrope-latin-400-normal-8tf8FM3T.woff`
- `D` `src/responsibleai/dashboard/static/whitepact/assets/manrope-latin-600-normal-BqgrALkZ.woff`
- `D` `src/responsibleai/dashboard/static/whitepact/assets/manrope-latin-700-normal-DGRFkw-m.woff`
- `R054` `src/responsibleai/dashboard/static/whitepact/assets/plus-ClT6l13R.js → src/responsibleai/dashboard/static/whitepact/assets/plus-BSgDfZIU.js`
- `R066` `src/responsibleai/dashboard/static/whitepact/assets/rotate-cw--wBcSNNH.js → src/responsibleai/dashboard/static/whitepact/assets/rotate-cw-DF3Ff9uL.js`
- `R096` `src/responsibleai/dashboard/static/whitepact/assets/scan-search-Dgmt_vhe.js → src/responsibleai/dashboard/static/whitepact/assets/scan-search-BaY3gKp2.js`
- `D` `src/responsibleai/dashboard/static/whitepact/assets/sora-latin-400-normal-OW7qkl5a.woff`
- `D` `src/responsibleai/dashboard/static/whitepact/assets/sora-latin-500-normal-w58xtEt9.woff`
- `R074` `src/responsibleai/dashboard/static/whitepact/assets/triangle-alert-Ddk67KlG.js → src/responsibleai/dashboard/static/whitepact/assets/triangle-alert-CC265jrm.js`
- `R085` `src/responsibleai/dashboard/static/whitepact/assets/users-CkSlSdj7.js → src/responsibleai/dashboard/static/whitepact/assets/users-RfuJWvH1.js`
- `M` `src/responsibleai/dashboard/static/whitepact/index.html`
- `A` `src/responsibleai/dashboard/static/whitepact/llms.txt`
- `A` `src/responsibleai/dashboard/static/whitepact/pages/about.html`
- `A` `src/responsibleai/dashboard/static/whitepact/pages/architecture.html`
- `A` `src/responsibleai/dashboard/static/whitepact/pages/contact.html`
- `A` `src/responsibleai/dashboard/static/whitepact/pages/developers.html`
- `A` `src/responsibleai/dashboard/static/whitepact/pages/docs.html`
- `A` `src/responsibleai/dashboard/static/whitepact/pages/enterprise.html`
- `M` `src/responsibleai/dashboard/static/whitepact/pages/home.html`
- `A` `src/responsibleai/dashboard/static/whitepact/pages/not-found.html`
- `M` `src/responsibleai/dashboard/static/whitepact/pages/pricing.html`
- `M` `src/responsibleai/dashboard/static/whitepact/pages/privacy.html`
- `A` `src/responsibleai/dashboard/static/whitepact/pages/private.html`
- `A` `src/responsibleai/dashboard/static/whitepact/pages/product.html`
- `M` `src/responsibleai/dashboard/static/whitepact/pages/refund-policy.html`
- `A` `src/responsibleai/dashboard/static/whitepact/pages/security.html`
- `M` `src/responsibleai/dashboard/static/whitepact/pages/sovereign.html`
- `M` `src/responsibleai/dashboard/static/whitepact/pages/terms.html`
- `A` `src/responsibleai/dashboard/static/whitepact/pages/trust.html`
- `M` `src/responsibleai/dashboard/static/whitepact/robots.txt`
- `M` `src/responsibleai/dashboard/static/whitepact/sitemap.xml`
- `M` `web/index.html`
- `A` `web/public/llms.txt`
- `M` `web/public/robots.txt`
- `M` `web/public/sitemap.xml`
- `M` `web/tooling/public-pages.ts`

### Tests / website CI

- `M` `tests/test_dashboard_api.py` — plaintext discovery regression now asserts current WhitePact boundary links and rejects obsolete certified-scoring claims; legacy resource endpoint tests are retained.

- `M` `.github/workflows/ci.yml`
- `A` `tests/js/corporate-website.e2e.mjs`
- `A` `tests/test_corporate_website_delivery.py`
- `M` `tests/test_paddle_website.py`

### Documentation

- `A` `docs/website/COMMERCIAL_SOURCE_OF_TRUTH_GAPS.md`
- `A` `docs/website/GLOBAL_INFORMATION_ARCHITECTURE.md`
- `A` `docs/website/GLOBAL_WEBSITE_DELIVERY_IDENTITY.md`
- `A` `docs/website/LEGACY_PUBLIC_SURFACE_DECISION.md`
- `A` `docs/website/PUBLIC_TRUST_BOUNDARY.md`
- `A` `docs/website/WHITEPACT_GLOBAL_WEBSITE_PHASE1_REPORT.md`

### Repository support

- `M` `.gitignore`
- `M` `package.json`
