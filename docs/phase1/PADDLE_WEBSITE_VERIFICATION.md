# Paddle website verification — internal release notes

Scope: public website only. Phase 1 checkpoint 4 remains paused. No Paddle SDK,
checkout, API, webhook, billing implementation, authority or execution changes.
Starting commit: `74736b9fa63ddde2391049d5fdd7d875e57dea5a`.

## Content and legal boundary

- Canonical URLs: `https://whitepact.com`, `/pricing`, `/terms`, `/privacy`,
  `/refund-policy`. `/refunds` permanently redirects to `/refund-policy`.
- React and generated static fallback use `web/src/content/commerce.json` as
  their common source. Vite emits route-specific metadata and no-JavaScript
  content to packaged `static/whitepact/pages/`. Rebuild with `cd web && npm run
  build`; commit generated assets with their sources. Unknown routes remain 404.
- Community is free; Pro and Enterprise retain contact/configuration-based
  pricing. `mcp/licensing.py::plan_catalog` has no numeric paid prices, and the
  existing homepage uses contact pricing. No price, quota or refund period was
  invented. Planned signed deployment identity is explicitly marked planned,
  not sold as an available feature.
- WhitePact is used as the project/service brand. No registered entity,
  registration number, office, tax identity or governing jurisdiction has been
  verified for this task. Founder must confirm the seller identity and contact
  details against the Paddle account before submission; counsel must review
  terms, privacy and refunds before relying on them as approved legal documents.
- The repository's older `TERMS_OF_SERVICE.md` and `PRIVACY_POLICY.md` contain
  historical drafts/operating commitments. The website no longer directs buyers
  to those as a second complete public policy. Counsel must reconcile the older
  retention commitments and operator assumptions with actual operations; this
  website edit is not evidence that earlier commitments were withdrawn or that
  retention jobs exist. No new retention or response deadline is promised here.
- No vendor super-admin, customer authority or security exemption is purchased.
  Self-hosting does not imply mandatory collection of customer agent activity.
  Stripe remains the existing integration, not an exclusive future provider.
- The broken `/.well-known/security.txt` navigation link was replaced with the
  repository's published `SECURITY.md` disclosure policy. No security runtime
  or disclosure-policy content changed.

## Provider requirements

Consulted Paddle's official [Domain Review guidance](https://www.paddle.com/help/start/account-verification/what-is-domain-verification)
on 2026-09-07. It asks for clear product and purchase information, accessible
policies, seller/brand identification and a live HTTPS site; custom pricing
documentation may be requested. Contact pricing is not a guarantee of approval.
Founder should supply a real custom quote/pricing document if requested. No
Paddle account approval, merchant-of-record activation or endorsement is claimed.

## Verification approach

- Public HTTP regression: `pytest tests/test_paddle_website.py tests/test_web_platform.py -q --no-cov`.
- Frontend: `cd web && npm test && npm run lint && npm run build`.
- Browser: `WHITEPACT_TEST_BASE_URL=http://127.0.0.1:8873 node tests/js/paddle-website.test.mjs`.
- Existing baseline: `WHITEPACT_TEST_BASE_URL=http://127.0.0.1:8873 npm run a11y`.
- Browser skill unavailable; used repository Playwright/Axe. Required flow:
  public URL -> readable page -> footer Refund Policy keyboard activation ->
  canonical policy page. Check desktop/mobile, refresh, real 404 and local links.
- Axe runs with JavaScript enabled. With JavaScript disabled, content, canonical
  metadata, links, keyboard focus/navigation and overflow are tested separately;
  an Axe attempt in that mode failed in the test runtime and is not counted as
  a passing Axe scan. Screenshots are outside the repository under
  `/private/tmp/whitepact-paddle-container-qa`.
- Test-only HTTP containers use in-memory data and may disable Secure cookies
  for authenticated accessibility setup. Production defaults remain Secure;
  never deploy the test authentication settings to a public host.

## External deployment boundary

Initial read-only requests timed out after 15 seconds. A later fresh HTTPS check
on 2026-09-07 returned `/` = 200 with title `ResponsibleAI · Governance Dashboard`;
`/pricing`, `/terms`, `/privacy`, `/refund-policy` and `/refunds` = 404. The unknown
route also returned 404. The live site has not received this website build.
Nothing was deployed or pushed; the live domain is **not ready for submission**.

Founder must deploy the resulting commit through the normal website host,
ensure `whitepact.com` DNS points at that deployment and valid HTTPS is served,
then recheck all five pages, footer links, `/refunds` redirect and real 404 from
the public internet. Only then submit the URLs to Paddle. Live issuer, enterprise
runtime and Phase 1 release claims remain outside this website task.

## Final local evidence

- Frontend: 25 tests passed; ESLint passed; TypeScript and production build passed.
  Existing large, lazy Trust Core chunk warning remains; no design/assets were
  regenerated other than ordinary compiled bundles and HTML.
- Python: 21 tests passed, including all canonical GET/HEAD routes, static
  metadata/fallback/footer, sitemap, robots, permanent redirect, real 404,
  headers and existing account/key lifecycle regression. Four pre-existing
  deprecated `RAI_*` environment-name warnings. Ruff and scoped app mypy passed.
- Earlier new route tests failed six checks against the original implementation;
  build errors and an eager test import that interfered with test environment
  setup were corrected before the final passing run. No production auth settings
  were relaxed to make application tests pass.
- Final production container: 20 combinations (5 URLs × desktop/mobile ×
  JavaScript on/off) passed content, metadata, footer, refresh and overflow.
  JavaScript-on Axe scans: zero serious/critical findings. Keyboard activation
  and visible focus passed in all four viewport/JavaScript contexts. Real 404,
  `/refunds` 308 and 11 distinct local-link targets passed.
- Existing accessibility baseline: 41 public routes plus 7 authenticated
  dashboard routes scanned successfully, including mobile checks. Its first
  authenticated attempt failed because Secure cookies were used with local HTTP;
  the documented test-only setting fixed the environment, not production code.
- Screenshots inspected: desktop pricing and mobile no-JavaScript refund page;
  readable, no clipping/overflow. Browser console/page-error assertions passed.
- Final local image ID:
  `sha256:999b506cbf2bb4fce82ef2b4c3a50ed6018a360df7d8363097ee5fed8ee1f652`.
  Built from the existing Dockerfile; non-root, read-only local execution,
  temporary/in-memory data only. Not a published or release-attested artifact.
- Staged Gitleaks: no leaks (about 655 KB scanned); SPDX and diff whitespace
  checks passed. Generated bundle renames reflect the changed import graph.

Repository pages are technically ready to deploy for domain review. This is not
Paddle approval, legal approval or Phase 1 enterprise readiness. Stop here;
resume checkpoint 4 only after a separate instruction.
