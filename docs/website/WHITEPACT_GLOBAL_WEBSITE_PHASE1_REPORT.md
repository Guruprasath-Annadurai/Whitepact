# WhitePact Global Website — Phase 1 Report

Date: 2026-10-04. Assessment concerns this local working candidate, not a deployed release.

This is the Phase 1 handoff snapshot before Phase 1B publication. Its uncommitted/CI-not-run statements describe that snapshot, not later qualification. See `PHASE1B_REVIEW_RECORD.md` and the separate exact-head CI evidence for successor state.

## Starting state and scope

- Starting/current HEAD: `52d9b3c5497af24bb7d4a7147e33deaadc64296e`.
- Isolated branch: `codex/whitepact-global-website-phase1`.
- Worktree: `/Users/ag/whitepact-global-website-phase1`.
- Changes remain uncommitted for owner review. No push, merge, tag, release, DNS change or deployment occurred.
- Canonical `/Users/ag/Whitepact` remains at the original detached HEAD; its unrelated untracked `docs/audit/` was preserved.
- React, TypeScript, Vite, routing, existing branding and product interfaces were retained. Python changes are limited to public HTML delivery, discovery content, real 404 delivery and the public-page CSP classification. No governance, authority, execution, database or migration semantics changed.
- Engineering guardrails informed isolated scope and fresh validation; frontend guidance informed accessible navigation, route splitting and retained static/reduced-motion fallbacks rather than a framework replacement.

## Delivery identity

The prior live audit observed a legacy ResponsibleAI surface and an anonymous authentication error. The deployed artifact SHA and proxy target were not established. Repository baseline already serves the corporate homepage at `/`; therefore a stale image or incorrect proxy is a hypothesis, not a proven root cause.

The application serves package-relative static assets. The dashboard image builds React into those packaged assets; a separate `/app/static` copy is not proof of the imported application's served asset identity. The implementation now gives public routes their own generated HTML, keeps authenticated shells noindex, and returns HTTP 404 for unknown public URLs without weakening API authentication.

Safe owner remediation: identify the live service/image SHA, imported module path, packaged HTML/assets and proxy root forwarding; compare them with the reviewed artifact; authorize correction/deployment only after that identity is proven; then anonymously verify public routes and protected API separation. Production delivery remains open. Detailed evidence and instructions are in `GLOBAL_WEBSITE_DELIVERY_IDENTITY.md`.

## Information architecture

Public structure: Home, Product, Architecture, Developers, Docs, Security, Enterprise, Trust, About, Contact, Pricing, Terms, Privacy, Refund Policy and the existing Sovereign page. Auth, onboarding, billing return and customer-console routes remain product surfaces, not public corporate landing pages.

One shared navigation connects the corporate routes. The conceptual control chain is maintained in one content constant:

Constitution → Identity → Authority → Intent → Policy → Capability Graph → Risk → Approval → Judgment → Short-Lived Execution Grant → Isolated Execution → Evidence → Audit → Revocation.

This is a conceptual explanation, not a claim that every configuration executes every stage. See `GLOBAL_INFORMATION_ARCHITECTURE.md` and `PUBLIC_TRUST_BOUNDARY.md`.

## Homepage

Positioning moved from broad agent/tool-control language toward an independently enforced runtime authorization boundary for supported, configured paths. The primary journey is documentation/local evaluation, not an unverified paid-hosted signup offer.

The exact doctrine is visible: the agent may think and plan freely but cannot act outside independently enforced authority. Prompt filtering, authentication and intent are distinguished from authority. Demonstrations and evidence samples are explicitly illustrative; denied authority cannot be approved into legitimacy. Scope and same-process trusted-computing-base limitations remain explicit.

The existing crafted head remains. Heavy 3D is opt-in, not an initial dependency; static mobile/reduced-motion fallbacks and a restrained desktop hero keep the explanation and CTA accessible.

## New and upgraded pages

| Page | Implementation |
| --- | --- |
| Product | New supported-path runtime governance explanation, limitations and evaluation entry. |
| Architecture | New conceptual chain, independent enforcement and trust-boundary explanation with pinned source references. |
| Developers | New implemented integration/distribution guidance and repository entry points; no invented npm SDK. |
| Docs | Useful local setup, authentication/API-key boundaries, actual request examples, MCP guidance, approval/denial/evidence/error and UNKNOWN semantics. |
| Security | New implemented-control versus deployed-validation versus external-assurance distinction. |
| Enterprise | New evaluation scope and evidence/operational prerequisites without invented certification or support SLA. |
| Trust | Explicit assurance and hash-chain verification boundaries; removed misleading check-badge presentation. |
| About | Clear doctrine, product purpose and qualified availability. |
| Contact | Neutral evaluation/contact presentation using the existing mechanism; no fabricated corporate email or support desk. |

## Truth corrections

- Pricing: historical Starter/Team and annual proposals are not treated as approved commercial offers. Public paid amounts are withheld pending owner reconciliation. Community/local evaluation and scoped hosted/enterprise evaluation remain available paths. Runtime PRO/ENTERPRISE mappings were not changed.
- Billing provider: privacy copy reflects repository Paddle-first behavior and guarded legacy compatibility, not an unconditional Stripe claim. Actual deployed provider remains an operational verification gate.
- Billing returns: redirects no longer assert payment receipt or unchanged subscription certainty. They instruct users to verify backend billing status.
- `llms.txt`: current WhitePact purpose, documentation and limitations replace obsolete ResponsibleAI scoring/tool-count terminology.
- Legacy surfaces: inventoried with an owner decision requirement; none were retired or deleted by this phase.
- Contact identity, legal approval and independently issued assurance remain unverified external gates. See `COMMERCIAL_SOURCE_OF_TRUTH_GAPS.md` and `LEGACY_PUBLIC_SURFACE_DECISION.md`.

## Navigation and accessibility

Shared desktop/mobile navigation, active-route indication, skip-to-main, mobile focus movement, Escape close and focus restoration are implemented. Demo tabs support keyboard navigation and correct tab-panel relationships. Scrollable documentation examples are keyboard reachable. Relevant login/signup/reset errors have field associations. Existing consequential product logic was not redesigned.

## SEO and delivery coverage

Fifteen public routes emit unique static title, description, canonical and social metadata plus noscript headings/navigation/editorial summaries. Auth/product shells are noindex without misleading public canonicals. Unknown public URLs return 404. Robots, sitemap and `llms.txt` are coherent with the expanded public routes. Structured data is not promoted into unsupported certification or unrelated SoftwareApplication claims.

Static fallback is editorial coverage, not full server-rendered React. Crawl/index behavior on the actual production host still requires post-deployment verification.

## Fresh validation

| Check | Result | Evidence/limit |
| --- | --- | --- |
| ESLint | PASS | `npm --prefix web run lint`; no errors or warnings. |
| TypeScript + production build | PASS | `npm --prefix web run build`; `tsc -b` and Vite succeeded. |
| Vitest | PASS | 7 files, 76 tests passed. |
| Python public delivery/commerce | PASS | 30 tests passed; includes public access with auth enabled, protected API 401, noindex shells and real 404. |
| Public browser/axe | PASS | 60 route/viewport scans; no critical/serious violations under the selected WCAG 2 A/AA and 2.1 AA rules. Not a full WCAG certification. |
| Responsive | PASS | 15 public routes at 375, 768, 1024 and 1440px; 60 layout checks, no whole-page overflow. |
| Keyboard/truth/no-JS | PASS | Mobile menu Escape/focus restoration, demo tabs/denial, reduced motion, no initial TrustCore request, 15 no-JS routes. |
| Existing customer browser journey | PASS | Real local backend with isolated disposable SQLite fixture; auth/onboarding/keys/members/approvals/evidence/UNKNOWN/security/logout assertions retained. Not PostgreSQL combined-RC proof. |
| Whitespace integrity | PASS | `git diff --check`. |
| GitHub CI / production host | NOT RUN | No push or deployment authorized. |

New browser proof: `tests/js/corporate-website.e2e.mjs`. New delivery proof: `tests/test_corporate_website_delivery.py`. Regression updates preserve truthful assertions rather than stale payment/pricing claims.

## Performance

Baseline main chunk: 279,563 bytes / 88,069 gzip. Current main is approximately 284.82 kB / 89.54 kB gzip. TrustCore remains approximately 884.45 kB / 235.19 kB gzip, unchanged in meaningful size and excluded from initial loading by browser proof. Corporate pages are a separate approximately 13.22 kB chunk. Vite's optional-large-chunk warning remains disclosed.

WOFF2-only declarations preserve the existing font families/weights and remove 118,808 bytes of redundant packaged WOFF assets; this is not claimed as an equivalent network saving. Existing large social/logo artwork remains unchanged. No measured field Core Web Vitals or Lighthouse score is claimed.

Generated hashed assets are part of the repository's tracked build output; their replacements/deletions accompany the successful rebuild, not removal of product functionality.

## Remaining gaps

### P0 — production launch blockers

- Live delivery identity/public-root mismatch remains unclosed: owner must prove the deployed artifact and proxy, then authorize and validate delivery correction. No production-ready assertion is justified.

### P1 — owner/release closure

- Approve one commercial source of truth: plans, prices, cadence, currency/taxes, legal entity and deployed provider. Public paid offers are deliberately gated until then.
- Confirm corporate contact identity and obtain appropriate legal/privacy/refund approval; do not substitute repository text for counsel approval.
- Run authorized CI/artifact packaging and post-deployment public/auth separation, discovery and asset parity checks. Confirm deployed SHA.
- Complete operational and external assurance prerequisites before making corresponding enterprise claims.

### P2 — practical improvements

- Brand-preserving social/image compression; remaining large artwork is not optimized in this phase.
- Additional screen-reader, zoom, manual contrast and lower-powered-device testing beyond the automated matrix.
- Field performance measurements, actual crawler behavior and longer-form developer integration examples after contract/owner validation.

### P3 — later scope

- Owner-approved legacy retirement, deeper editorial case studies and future Sovereign documentation only when supported by canonical implementations.
- Broader visual polish after functional/delivery closure; no further redesign started.

## Updated readiness — explicit audit rubric

This is an editorial checklist assessment, not a coverage percentage, certification or enterprise-readiness claim. Same 14-domain, ten-check audit approach: met = 1, partial = 0.5, unverified = 0. CI, live delivery, external assurance and field performance are not awarded as proven.

| Domain | Points / 10 |
| --- | ---: |
| Visual foundation | 7 |
| Homepage | 8 |
| Messaging | 8 |
| Developer experience | 7 |
| Enterprise/security | 6 |
| Architecture explanation | 7 |
| Content | 7 |
| SEO | 8 |
| Performance | 7 |
| Accessibility | 8 |
| Mobile | 8 |
| Conversion | 7 |
| Technical delivery | 8 |
| Launch gates | 5 |
| Total | 101 / 140 |

Working-candidate repository readiness: approximately **72%**, versus prior approximately 54%. The prior live evidence remains 1/10, unchanged; using the same 70% repository / 30% live weighting gives approximately **54% global readiness**. No fresh deployed-host evidence is implied. Binary production launch gate: **FAIL / OWNER ACTION REQUIRED**.

## Owner review and status

Review the local diff and five companion website documents. Approve commercial/contact/legal facts and the operational identity-remediation plan separately. Commit/publication/deployment require their own authorization. No core product functionality, production billing state or external infrastructure was changed.

WhitePact global corporate website Phase 1 truth, delivery-identity and information-architecture implementation is complete and ready for owner review. No production deployment has occurred.
