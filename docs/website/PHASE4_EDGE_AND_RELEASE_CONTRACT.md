<!-- Copyright (c) 2026 Guruprasath Annadurai; SPDX-License-Identifier: MIT -->
# Website production edge and release contract

Primary references checked for this contract:
[Cloudflare Full (strict)](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/),
[HSTS behavior and preload implications](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Strict-Transport-Security),
[RFC 9116 security.txt](https://www.rfc-editor.org/rfc/rfc9116.html).
Full (strict) requires a valid matching origin certificate; this is not evidence
that WhitePact's origin has been configured. HSTS rollout below is a conservative
project strategy, not a claim of provider deployment or preload approval.

## Delivery boundary

This contract covers **public website** routes only. Do not apply this CSP or
shared cache configuration to the authenticated product, Paddle checkout or MCP
routes without the corresponding product owner's validation. Existing Python
runtime semantics are unchanged. Implementing these requirements at an origin or
edge is an infrastructure-owner action, not performed by Phase 4.

Canonical metadata origin is `https://whitepact.com`. Public build variables:
`VITE_WHITEPACT_SITE_ORIGIN` and `VITE_WHITEPACT_SITE_PROFILE` (production,
staging, development, test). Production rejects noncanonical origins; staging
requires public HTTPS and forces noindex. Local tests may explicitly use a
loopback origin. No server credential belongs in a `VITE_*` variable. The
existing Paddle client token is a public client credential for the product UI,
not a server API key and not required for the public website.

Server session, CSRF, encryption, database, email and Paddle server credentials
are SERVER-SIDE CONFIG / SECRET, never website build inputs. Security/legal/
commercial decisions are OWNER INPUT. Analytics and cloud credentials are NOT
REQUIRED. DNS/TLS/edge deployment are external configuration, not Vite config.

## Headers and caching

Normative machine contract: `web/tooling/launch-contract.mjs`.

- CSP: self-only scripts/styles/images/fonts/connections; no framing, objects
  or base URLs; self-only form actions. No unsafe-inline/eval exceptions.
- X-Content-Type-Options: nosniff.
- Referrer-Policy: strict-origin-when-cross-origin.
- Permissions-Policy: camera=(), microphone=(), geolocation=().
- HSTS initially max-age=300 **only after HTTPS validation**. Owner may increase
  to 86400, then 31536000 after rollback/TLS evidence. Do not add includeSubDomains
  until every subdomain is reviewed. No preload submission or preload directive.
- HTML/errors/unversioned assets: no-cache (revalidate); do not cache a 404 as 200.
- Content-hashed JS/CSS/fonts: public, max-age=31536000, immutable.
- robots/sitemap/llms: public, max-age=300.
- Authenticated/private responses: private, no-store; never shared cache.

COOP/CORP are not mandatory: product popup/embedded behavior needs separate
review. Do not globally override product headers with public-site policy.

## Budget-conscious Cloudflare requirements (not applied)

Full (strict), valid origin certificate and hostname verification, HTTPS redirect,
HTTP/2 enabled; HTTP/3 optional where available; Brotli/gzip compression with
correct Vary behavior. Do not assume paid rules/WAF features. Public GET/HEAD
only; reject other methods at the public static surface without breaking product
APIs. Preserve public HTTP 404 and permanent `/refunds` redirect. Never rewrite
API errors into HTML 200. Serve discovery files at root and omit private routes
from the sitemap. Staging blocks indexing; production permits only public routes.

Cloudflare → public LB → private SaaS origin remains a separate Gate 2 design.
Public website routing must preserve authenticated-origin protection; no direct
origin credential in HTML or JavaScript. Do not mint certificates or configure
accounts/DNS in this phase.

## Artifacts, ordering and rollback

`node web/tooling/launch-contract.mjs manifest` produces deterministic JSON
with Git SHA/tree, Git commit epoch (not wall-clock build time), route/file
counts and SHA-256 of every output file. Capture it outside the artifact set;
`verify <manifest-path>` checks exact identity and all bytes. A digest manifest
is not a signature or independent build attestation. Generate it only after the
candidate is committed, from a clean checkout. Retain the qualified artifact
and manifest together. No local absolute paths are embedded.

Deploy new hashed assets **before** atomically activating new HTML. Retain old
hashed assets while old HTML may be cached or open in a browser. Verify both
old and new HTML dependencies; do not delete the old set on activation. Retain
unhashed shared assets compatibly or version them before incompatible changes.
Rollback selects the prior qualified artifact/HTML and its asset set. Repository
rollback is a separate reviewed revert/new branch; never rewrite the qualified
history. Infrastructure rollback is owned by the chosen platform; no invented
cloud command is supplied. Trigger rollback on TLS/header/route/privacy failure,
missing assets, or failed acceptance checks. Serve `maintenance.html` with HTTP
503, no-store and Retry-After if temporarily necessary; never return it as a
success page. Do not expose framework traces.

Production source maps are disabled; this is release hygiene, not a security
boundary. Reproducibility requires two clean locked installs/builds with equal
file hashes. Commit-time manifest identity is separate from byte reproducibility.

## Acceptance commands and limits

```
node web/tooling/launch-contract.mjs audit
node --test tests/js/website-launch-contract.test.mjs
BASE_URL=https://explicit-approved-staging-origin node web/tooling/launch-contract.mjs smoke --staging
```

No remote target is implicit. Running a command against production requires
separate authorization. The smoke command is read-only and rejects insecure
remote targets; local preview uses explicit `--local`, which does not prove
DNS/TLS/Cloudflare. Runtime certificate validation stays enabled.

Deeper post-deploy browser qualification must re-run Phase 3's Playwright
route/axe/responsive/no-JS/privacy/keyboard/reduced-motion checks against the
actual target. Check HTTP→HTTPS redirect, certificate SAN/chain/expiry, HSTS,
cache behavior, external links and old/new asset coexistence with infrastructure
evidence. A local preview cannot certify these external gates. Field CWV/INP
needs field measurement; lab LCP is not a field claim.

## Security contact activation

No security.txt is published until OFFICIAL_SECURITY_CONTACT_REQUIRED closes.
Infrastructure must then serve `/.well-known/security.txt` with an approved
Contact URI, future Expires, Canonical HTTPS URI and optional policy/language;
`/security.txt` may redirect to the canonical path. Verify owner approval and
delivery; reject dummy/example contacts. Never guess a personal address. The
existing disclosure-policy link remains available. Legal identity placeholders
must not ship; unresolved owner decisions stay explicit in the register.

## Regression budgets and inventory commands

Deterministic CI budgets: each compressed JS chunk <=100 KB; each compressed
CSS chunk <=20 KB. Existing Phase 3 source-bound initial-load checks remain
required. Review lab medians against mobile LCP 3000 ms, desktop 800 ms, CLS
0.1, transfer 750 KB and <=24 initial requests; timing/environment-dependent
metrics trigger investigation, not flaky automatic CI failures. Qualified Phase
3 independently observed approximately 2412/448 ms mobile/desktop LCP and
near-zero CLS. Always disclose the actual Phase 4 lab comparison, including
transfer/DOMContentLoaded tradeoffs. No field CWV or INP claim.

`node web/tooling/launch-contract.mjs inventory` emits a machine-generated
package/namespace inventory with source-relative file and line locations.
Manual-review classifications are deliberately not automatically marked
defective. Review every future package migration against this inventory and
the actual public documentation; publication and owner approval remain gates.
`npm run audit:website-postdeploy` requires an explicit BASE_URL and prepares
HTTPS/header/cache/redirect checks plus JS/no-JS, mobile/desktop, axe, storage,
cookie and external-network checks. Never run it against production in Phase 4.
This harness blocks off-origin subresources; separately approved external-link
validation must not be confused with privacy resource loading.

## Package and developer identity

Retain `rai-governance-platform` until founder locks a published replacement.
`responsibleai` is an implementation namespace, not automatically a branding
defect. `rai-client` may be compatibility identity. `whitepact` and
`whitepact-client` must not be advertised as published installers without proof.
Inventory public installation commands separately from internal namespaces and
historical mentions. Do not invent a release tag or modify runtime versioning.
Current qualified source pins remain deliberate evaluation references, not a
promise of the latest stable release.
