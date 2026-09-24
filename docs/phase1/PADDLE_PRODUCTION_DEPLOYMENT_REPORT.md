# Pricing closure and production deployment boundary

Date: 2026-09-07. Branch: `integration/enterprise-phase1`.
Starting revision: `a4a6e97f5ea1b39f433daecf989293cfe9d3024e`.
The commit containing this report is the local pricing candidate; use
`git log -1 --format=%H -- docs/phase1/PADDLE_PRODUCTION_DEPLOYMENT_REPORT.md`
to resolve its exact SHA. It is **not a production deployment record**.

## Commercial decision

All amounts are USD. Community is $0 forever ($0 annually), Cloud Starter
$29/month or $290/year, Cloud Team $99/month or $990/year, Enterprise / Private
custom. Annual cloud pricing equals ten monthly payments: two months free,
without a percentage claim. Cloud tiers are Early Access inquiries via the
existing contact route, not purchasable entitlements. Community links to the
repository quick start. Enterprise requires a negotiated agreement.

React homepage, pricing page and static no-JavaScript fallback share the same
plan data. Existing runtime FREE/PRO/ENTERPRISE billing models and Stripe
fulfillment are unchanged; Starter and Team are commercial proposals, not new
runtime enum values. No Paddle SDK, checkout, webhook, product or price created.

## Feature evidence boundary

| Claim | Classification | Treatment / evidence |
|---|---|---|
| MIT core and self-managed use | IMPLEMENTED | LICENSE, repository quick start, core modules; public Community description |
| Hosted service and organization collaboration | PARTIAL | Existing web-platform tests exercise accounts, organizations and credentials; new commercial tiers not fulfilled; Early Access only |
| Enterprise deployment/support | PARTIAL | Evaluation and negotiated scope only; no availability or support guarantee |
| SSO/SCIM production service | UNVERIFIED | Removed from pricing promises; homepage explicitly does not promise availability |
| Signed deployment identity | PLANNED | Not included in pricing cards; Phase 1 remains paused |
| SLA, retention guarantees, FDE, air-gap availability, certifications | UNVERIFIED | Not advertised as live pricing capabilities |

Removed old homepage test-key limit and claim that pricing directly maps to live
entitlements. Security fixes are not presented as paid-only. Legal content was
cross-checked and left unchanged: monthly/annual terms are order-specific,
payment-provider wording is conditional, statutory refund rights preserved.
Seller identity remains unconfirmed; no counsel approval evidence exists.

## Local verification

- Frontend: 27 tests passed, ESLint passed, TypeScript and Vite production build passed.
- Existing lazy TrustCore chunk remains about 884 kB; build warning, not hidden.
- Python public/legal/web-platform regression: 21 passed, four existing deprecated-environment warnings.
- Browser matrix: 20 page/viewport/JavaScript combinations; 1440px and 390px,
  JS enabled and disabled. Exact prices, Early Access, CTAs, canonical metadata,
  public footer, reload, keyboard navigation and overflow checks passed.
- Axe: ten matrix scans plus existing 41 public and seven authenticated route
  scans passed the serious/critical gate. This is not full accessibility certification.
- Eleven internal-link targets, real 404, permanent 308 refund redirect passed.
- Public route tests cover sitemap, GET/HEAD, CSP and nosniff.
- Gitleaks staged diff: no leaks. SPDX, documentation consistency and diff checks passed.
- Pricing mobile screenshot inspected; no layout overflow. Screenshots are local
  QA artifacts, not production evidence.

## Production: NOT DEPLOYED

Render access in the controlled browser ends at sign-in. No authenticated target
service settings, supported direct-upload path, build ID or production source SHA
were verified. No Render CLI or repository production deploy workflow was found.
`scripts/deploy.sh` is self-hosted Docker setup, not the existing Render deployment.

[Render's official deployment documentation](https://render.com/docs/deploys)
describes deploying a specific commit from a linked repository, or an existing
registry image. It does not establish an available local-worktree upload path for
this target. A Git-backed deployment of this local-only candidate would require
publishing it first; no Git push is authorized. Do not bypass that restriction,
change the target service or deploy a different revision.

Public HTTPS checks at approximately 17:24 UTC used curl with normal certificate
validation after the initial Node client timed out:

| Route | HTTP | Result |
|---|---|---|
| / | 200 | Old ResponsibleAI governance dashboard, no canonical or refund footer |
| /pricing | 404 | No current pricing |
| /terms | 404 | Required page absent |
| /privacy | 404 | Required page absent |
| /refund-policy | 404 | Required page absent |
| /refunds | 404 | Required permanent redirect absent |
| /definitely-does-not-exist | 404 | Correct status |

Live responses expose HSTS and nosniff, but still use the legacy CSP allowing
inline scripts and external script CDNs; they do not prove the candidate headers
are deployed. Cloudflare reports DYNAMIC. This is not evidence of a successful
CDN purge. Live mobile/no-JavaScript acceptance remains blocked by stale content.

Deployment ID/digest/timestamp: NOT AVAILABLE (no deployment performed).
Paddle domain readiness: NO. Approval: EXTERNAL PENDING. Checkout readiness: NO.
Phase 1 checkpoint 4 resumed: NO. Pushed: NO. Merged: NO.

Next gate: authenticated access to the existing Render service and an explicitly
authorized way to make this exact candidate available to its build mechanism.
No production or enterprise readiness claim follows from these local checks.
