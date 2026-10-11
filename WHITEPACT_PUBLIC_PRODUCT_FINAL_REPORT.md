# WHITEPACT — PUBLIC PRODUCT EXPERIENCE FINAL REPORT

Date: 2026-10-07. Scope: public website, developer entry, public documentation, claims, accessibility and read-only acceptance/deployment preparation. This report is not production authorization or independent qualification.

Historical local finalization checkpoint. The final successor closeout supersedes branch, commit and CI status below. Its temporary-index snapshot omitted the subsequently explicitly tracked claims JSON because of the inherited JSON ignore rule; it is not the complete successor identity.

## A. VERDICT

PUBLIC PRODUCT EXPERIENCE — CONDITIONAL

The authorized public implementation is complete locally and the final public gates below PASS. Global launch remains conditional on a committed successor/exact-SHA CI and independent qualification, plus the isolated owner/package/live inputs in T–V. No successor commit, GitHub CI or independent qualification is claimed. The qualified ancestor remains unchanged; there is no known remaining P0/P1/P2 public website defect.

## B. BASE SHA/TREE

- Qualified ancestor: `c9622a2539f20314205e1c30a0f4b8de3927b8f4`.
- Qualified tree: `bf04e0022dd42d0463ec69aa0f942ff5b10c5dea`.
- Read-only GitHub check: PR #148 OPEN, DRAFT, `mergedAt:null`, exact ancestor head preserved.

## C. FINAL BRANCH

`codex/whitepact-global-website-finalization` in the dedicated finalization worktree. One consolidated finalization branch; earlier workstream worktrees were preserved, not merged into the qualified branch.

## D. FINAL SHA/TREE

HEAD remains the qualified ancestor above. Implementation is **uncommitted**; that HEAD does not identify the modified source. No new candidate SHA exists. The exact implementation tree is `27f84d14a7bcf64e45e4ffa44342561f93081f12`, generated through a temporary index without staging the real index or creating a commit. It differs from the ancestor in 60 files (1,480 insertions, 137 deletions); this report is an additional file excluded from that snapshot to avoid self-reference. The modified Python/backend/SDK/CLI/infrastructure path inventory is empty.

## E. ROUTE INVENTORY

All routes below have static, route-specific public HTML and hydrated React surfaces. Their source is `web/src/content/{corporate,commerce,public-info}.json`, public marketing components and the public-only Sovereign page.

| Route | Purpose | Local status |
|---|---|---|
| `/` | Runtime authorization boundary and evaluation entry | Tested |
| `/product` | Supported-path product/control model | Tested |
| `/architecture` | Control chain, authority versus infrastructure | Tested |
| `/developers` | Source, integration and release prerequisites | Tested |
| `/enterprise` | Buyer evaluation and deployment boundary | Tested |
| `/security` | Controls, limitations and reporting process | Tested |
| `/trust` | Evidence and qualification boundaries | Tested |
| `/sovereign` | Public product explanation; deployment-dependent availability | Tested |
| `/docs` | Source-pinned setup, API/MCP, approvals, UNKNOWN and evidence | Tested |
| `/about` | Product identity and open-source model | Tested |
| `/contact` | Current factual evaluation contact | Tested |
| `/pricing` | Commercial state, not invented entitlement | Tested |
| `/privacy` | Privacy disclosure and owner boundaries | Tested |
| `/terms` | Explicit owner-gated legal content | Tested |
| `/refund-policy` | Commercial/legal prerequisites | Tested |
| Unknown public path | Readable HTTP 404, noindex, Return home | Tested |

`/refunds` redirects to `/refund-policy`. `/dashboard/evidence` and `/sovereign/workbench` are existing private product entry points, not newly created public routes. `/api/docs` is an authentication-protected reference, not a fabricated static page.

## F. 200% ZOOM STATUS

The original reproduced homepage case at viewport 375 had `clientWidth=375`, `scrollWidth=640` after CSS zoom 2. The global 320px body minimum became a 640px physical floor. Further strict checks identified intrinsic header/footer navigation widths, nonwrapping scenario controls, the Inspect decision button at 1024, and the public Sovereign hero's minimum grid track.

Root fixes are public-scoped in `web/src/corporate.css`: remove the public body floor; wrap navigation/controls; allow text and intrinsic children to shrink; use available-width container queries for the demo and public Sovereign layout. No body overflow concealment was added. Workbench and authority logic were not changed.

Final matrix PASS: 15 routes × 320/360/375/390/412/768/1024/1280/1440 = 135 CSS-200% cases, with no reported page-wide overflow or clipped interactive target. Interactive-target bounds are checked separately from page-wide overflow. Contained code/table scrolling is not misreported as page overflow. CSS reflow, text enlargement and narrow-width equivalence are not proof of every browser's native/OS zoom implementation. Evidence: terminal exit 0, 13/13 tests in `acceptance10.log`; all nine zoom widths completed.

## G. ACCESSIBILITY STATUS

TESTED: final corporate suite completed 150 axe scans with zero failures, keyboard navigation, skip links, menu focus/escape/restoration, meaningful link activation, reduced motion, 15 route text-enlargement/reflow checks and no-JS navigation. `tests/js/corporate-website.e2e.mjs` and `web/tooling/acceptance/browser.mjs` own these probes.

STATICALLY VERIFIED: semantic headings, labeled controls, landmarks, public code-copy announcements/failure fallback and focus styles. This is practical WCAG-oriented engineering evidence, not certification or a complete manual screen-reader audit. Browser proof is Chromium; cross-browser/assistive-technology qualification is not invented.

## H. RESPONSIVE STATUS

TESTED: 150 final corporate layouts at 320/360/375/390/412/768/1024/1280/1440/1920. Strict acceptance additionally checks 375/768/1024/1440 styled layouts, nine CSS-zoom widths and separate degraded-mode observations. Final results are recorded in S; overflow under deliberately blocked CSS is kept separate from styled-layout defects.

## I. PERFORMANCE STATUS

Production artifact audit PASS: initial JS 308,359 bytes (budget 310,000), initial CSS 79,975 (budget 80,000), home HTML 30,431 (budget 40,000), font assets 101,868, social asset 448,345. No TrustCore 3D JS chunk is required by the public build. Optional/shared image files in the artifact inventory are not represented as initial route downloads. Fonts are self-hosted.

The first layout fix exceeded the unchanged CSS budget at 80,798 bytes. Unused optional-core/footer selectors and redundant overrides were removed; the budget was not raised. No private console styling or runtime semantics were redesigned.

Serialized laboratory run after all browser gates: Chromium 151.0.7922.34, cache disabled, three mobile + three desktop runs. Mobile profile: 390px, 150ms latency, 200,000 bytes/s, CPU ×4; desktop: 1440px, 40ms latency, 1,250,000 bytes/s, CPU ×1. Medians:

| Profile | LCP ms | CLS | Transfer bytes | DOM-ready ms | Load ms | Long-task total ms |
|---|---:|---:|---:|---:|---:|---:|
| Mobile | 2432 | 0 | 655733 | 3581.6 | 3587.1 | 87 |
| Desktop | 456 | 0.000020246 | 655733 | 621.2 | 622.3 | 0 |

Optional 3D loaded: false in all six runs. Compared with the recorded Phase 4 lab figures (mobile 2436ms, desktop 448ms, transfer 652122), transfer increased 3,611 bytes; desktop LCP was 8ms higher and mobile 4ms lower. These small differences are not a causal improvement claim or a controlled cross-version baseline. No field CWV, INP, production-compression or hydration-performance improvement is claimed. Raw local evidence: `performance-final.json` and `tests/js/corporate-performance.mjs`.

## J. PRIVACY STATUS

TESTED: corporate public browsing attempts no external-origin request or protected API call, sets no cookies, and writes neither localStorage nor sessionStorage. No public analytics, remote fonts, tracking embeds or telemetry were added. Explicit outbound GitHub links and mailto evaluation links are user navigation/contact mechanisms; separately authorized link-check requests are test traffic, not visitor tracking. Private console/Paddle behavior is outside this public browsing assertion.

Secret scan: `gitleaks dir web --redact --no-banner` PASS, no leaks found. Pattern scanning is not a universal secret-absence proof.

## K. SECURITY HEADER STATUS

STATICALLY VERIFIED + local contract TESTED: existing CSP, Referrer-Policy, nosniff, frame protection, Permissions-Policy, private no-store/indexing isolation, canonical host/profile rules and staged HSTS contract are preserved in `web/tooling/launch-contract.mjs` and Phase 4 release contracts. The acceptance harness uses verified hostname/CA TLS and the explicit HTTPS target port, refuses disabled TLS validation, and requires explicit external-target opt-in.

LIVE TEST PENDING: real certificate chain/renewal, HSTS/HTTPS redirect activation, DNS/CDN/origin topology, real response compression/cache behavior and production edge headers. Local fixture headers are not claimed as deployed headers.

## L. SEO STATUS

TESTED artifact audit: 15 unique static titles/descriptions/canonicals, Open Graph/Twitter metadata and image alt descriptions, one static H1 per route, parseable JSON-LD, coherent robots/sitemap/llms, private-route exclusion and readable noindex 404. Staging noindex is an explicit deployment profile. No keyword stuffing, certification/traction schema or package-publication claim was introduced.

## M. BROKEN LINK STATUS

One genuine public link was corrected: repository quick start now targets the existing `#30-second-quickstart`, not nonexistent `#quick-start`. Eighteen distinct public repository/documentation URLs returned HTTP 200 in credential-free HEAD checks; pinned source paths were also verified against commit `52d9b3c5497af24bb7d4a7147e33deaadc64296e`. The anchor was checked against the README heading.

Hydrated links are now included in acceptance, not only static HTML. The static fixture was corrected for existing private Evidence/Workbench routes and the protected API reference; production authentication was not altered. Final internal-link gate PASS in `acceptance10.log`. Mailbox delivery and owner identity are OWNER INPUT REQUIRED, not falsely validated by a mailto link.

## N. PRODUCT STORY STATUS

Implemented content explains the independent pre-execution authorization boundary, authentication versus action authority, connected MCP/agent placement, consent/policy/approval/revocation and UNKNOWN outcomes. It preserves the conceptual fourteen-stage chain: Constitution → Identity → Authority → Intent → Policy → Capability Graph → Risk → Approval → Judgment → Short-Lived Execution Grant → Isolated Execution → Evidence → Audit → Revocation.

The chain is a conceptual model, not a claim that every deployed adapter exercises every stage. Six formerly unbounded doctrine copies are scoped to supported, configured enforcement paths. Direct calls outside those paths and compromised infrastructure are not universally controlled.

## O. DEVELOPER EXPERIENCE STATUS

Source-pinned local setup, actual authentication/API/MCP examples, server-controlled approval semantics, evidence-list/session-detail distinction and UNKNOWN handling are available. Source SDK/CLI references are separated from package publication. Public `pip install whitepact` is not advertised. `package-release.ts` defaults publication evidence to null; its tests require verified registry/source/artifact/version/install evidence before instructions appear.

No Sovereign authority, topology, risk, simulation or fabricated history is computed by the public site. Existing SDK evidence-detail helper mismatch is explicitly disclosed and handed to Cursor, not presented as a working example.

## P. ENTERPRISE EXPERIENCE STATUS

Product/architecture/security/enterprise routes explain tenant isolation, role/identity boundaries, approval, revocation, evidence and deployment/operator responsibilities. Developer, AI infrastructure and founder/investor evaluation paths use concrete criteria rather than customer/scale/certification claims. Contact remains a neutral evaluation mechanism, not an invented staffed sales/support operation or SLA.

## Q. CLAIMS REGISTER

Definitive register: `docs/website/truth/public-claims.json`; explanation: `docs/website/WEBSITE_PUBLIC_CLAIMS_REGISTER.md`. Exact source/line/quote/route coverage: 559 fragments. Classification counts: SECURITY_DEPENDENT 235; CLOUD_DEPENDENT 149; LEGAL_DEPENDENT 58; PROVEN 38; COMMERCIAL_DEPENDENT 27; OWNER_INPUT_REQUIRED 27; PACKAGE_DEPENDENT 25; REMOVE_OR_REWRITE 0.

Six claims-register tests PASS against current public source. PROVEN is source/boundary evidence, not production availability. Conditional claims remain visibly scoped; Antigravity engineering qualification is not external certification. No SOC2/ISO, uptime/customer/scale claim or paid entitlement is invented.

## R. BUILD STATUS

`npm --prefix web run build` PASS (TypeScript + Vite); release artifact audit PASS under unchanged budgets. Generated public artifacts are part of the uncommitted implementation. No new framework, dependency or lockfile change was required. A second serialized build and an isolated fresh locked install/build both produced the same 58-file inventory with zero added/missing/changed SHA-256 hashes. The isolated build used the exact implementation tree's `web/` plus its unchanged SDK TypeScript types and canonical JSON contracts. This is same-host deterministic build proof, not cross-platform supply-chain qualification.

## S. TEST COUNTS

- ESLint PASS.
- Vitest: 114 passed, 0 failed.
- TypeScript/production build PASS.
- Claims/deployment/launch Node tests: 30 passed, 0 failed (6 + 13 + 11).
- Final acceptance unit tests: 14 passed, 0 failed, 0 skipped, including allowlisted TLS/network cause diagnostics and secret-safe human output.
- Corporate browser: 150 axe + 150 responsive checks, 15 no-JS routes, keyboard/truth/reduced-motion/text-scaling PASS, failures `[]`.
- Final strict browser acceptance: 13 passed, 0 failed, 0 skipped, terminal exit 0. The browser fixture exercised 345 traversals: 60 styled/axe, 135 CSS-200%, and 30 each no-JS, blocked-assets, reduced-motion, slow-network and offline-after-load. Internal links PASS. The later reporting-only transport-diagnostic helper/test was validated by the final 14-test unit run; browser logic and all 58 public artifacts remained unchanged. External TLS/maintenance/rollback/owner-contact remain deliberately UNVERIFIED, so this local result does not claim external acceptance.
- Repeat build: 58/58 files byte-identical; added/missing/changed files 0.
- Isolated fresh install/build: PASS, 58/58 files byte-identical, from a disposable clean build directory. Initial narrow-archive attempts omitted imported SDK types/contracts and failed compilation; restoring those unchanged snapshot inputs fixed the test environment without any source change.
- Serialized performance: six runs completed; exact medians in I.
- npm audit: 0 total advisories; no audit error. This does not clear Python/default-branch/product advisories.
- Gitleaks web scan PASS; syntax and diff checks PASS.

Historical local evidence files: `corporate8.log`, `vitest7.log`, `node-final.log`, `acceptance-unit-final14.log`, `acceptance10.log`, `build8.log`, `rebuild-final.log`, `clean-install.log`, `clean-build-final.log`, `performance-final.json`, `secret-final.log`, and `npm-audit.json`. Logs are local evidence, not an immutable release publication. Frontend lint/type/build and 114 component tests are not proof of unrelated backend/runtime security; no new backend suite or exact-successor GitHub CI is claimed here.

Earlier failures are retained: original zoom/clipping failures; CSS budget failures; sandbox npm/localhost/Chromium environment failures; static fixture missing protected/private linked routes. No failed run is called green. The final terminal runs supersede those attempts only for the corrected, scoped conditions.

## T. LIVE-ONLY ITEMS

Real staging/production TLS, DNS, canonical HTTPS redirects, HSTS rollout, CDN/cache/compression/origin protection, external acceptance, maintenance response, actual activation/rollback rehearsal and field performance. Prepared tooling does not activate any of them. External acceptance deliberately remains NOT ACCEPTED when required checks are UNVERIFIED.

## U. CURSOR DEPENDENCIES

Canonical package publication/reproducible installation and source/version/artifact identity; SDK `get_evidence`/`getEvidence` detail-route compatibility; exact combined-runtime selected-adapter security qualification; hosting/authenticated MCP and product-release validation. No SDK, CLI, IAM, database, approval engine, grant or backend Python changes were made here.

## V. OWNER INPUTS

Approved legal identity/jurisdiction/policies; corporate evaluation/support/security contact and security.txt owner approval/expiry; commercial offers/pricing/billing availability; production domain/deployment authorization and operational ownership. Current neutral/gated copy does not fabricate these inputs.

## W. P0/P1/P2/P3

Known remaining public website defects: P0 0; P1 0; P2 0; P3 0. These are findings from the tested scope, not a claim of universal defect absence. Live, owner, package and combined-security release gates are separate from website defect counts. Formal certification, field INP/CWV and complete manual assistive-technology/cross-browser qualification are not claimed. Future observations can reopen findings; none is suppressed to obtain this result.

## X. EXACT REMAINING WEBSITE WORK

No known remaining authorized public UI/content/zoom/harness implementation task. Completed: scoped reflow fixes, product/conversion copy, package/claim gates, useful source-pinned docs, corrected link, consolidated acceptance/deployment tooling and final local validation.

Release work still required: authorize and record a successor commit from the exact implementation snapshot; run exact-successor CI and independent qualification; supply T–V inputs; execute explicitly authorized external staging acceptance/maintenance/rollback and later production acceptance. No new Codex product-design phase is required to hide an unfinished website feature. The ancestry rehearsal in `docs/website/FINAL_INTEGRATION_REHEARSAL_REPORT.md` is non-merging and does not qualify inherited backend changes or a future moving main branch. No report-only commit, merge, deployment or production activation was performed.

NO MERGE

NO DEPLOY

NO DNS MUTATION

NO CLOUD MUTATION
