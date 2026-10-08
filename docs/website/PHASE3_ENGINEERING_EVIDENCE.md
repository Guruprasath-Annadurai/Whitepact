# Website Phase 3 engineering evidence

Status: local qualification passed; not independent qualification, public
deployment, commercial activation or a product release. Exact-head GitHub CI
must still run on the successor commit. Do not reuse Phase 2's green runs.

Base: `1634c542e49039828e1913c9f01ff63bb4be1de2`, tree
`5ccbd0d633173c2becd33521cde7db28aa6f2ce5`. Substantive Phase 2 parent:
`837d1c6ac019fac81113fa908155acaf81d7c5d4`. Phase 1 ancestor:
`f970e7c4e210f339c8c7af2104ea98546ad6b514`.

## Performance method and tradeoff

Harness: `node tests/js/corporate-performance.mjs`, Chromium 151.0.7922.34,
headless, localhost uncompressed production files, cache disabled, reduced
motion, 900px height, three fresh navigations per profile. Mobile: 390px,
150ms latency, 200,000 bytes/s, 4x CPU. Desktop: 1440px, 40ms,
1,250,000 bytes/s, 1x CPU. Host variance applies. No field CWV, INP, production
uptime or Lighthouse score is claimed.

Fresh Phase 2 baseline LCP samples: mobile 2996/2624/2660ms; desktop
548/560/548ms. Baseline median mobile CLS 0.040949; desktop 0.025591.

| Metric | Fresh Phase 2 median | Phase 3 observed median |
| --- | ---: | ---: |
| Mobile LCP | 2660ms | 2376ms |
| Mobile CLS | 0.040949 | 0 |
| Mobile DOMContentLoaded | 2346.9ms | 3536ms |
| Mobile long-task duration | 133ms | 72ms |
| Desktop LCP | 548ms | 444ms |
| Desktop CLS | 0.025591 | 0.00002025 |
| Desktop DOMContentLoaded | approximately 421ms | 617.4ms |
| Transfer bytes, either profile | 626572 | 651227 |

Final uncontended Phase 3 LCP samples: mobile 2516/2324/2376ms; desktop
444/448/436ms. Median LCP improves by 284ms (10.68%) mobile and 104ms (18.98%)
desktop. An earlier series overlapped the tail of unit tests and is not used
for these medians. Experimental measurements with incorrect asset URLs are
excluded. The correct production base is explicitly regression-tested.

Build-time public HTML lets users read the home message before application JS.
It improves measured LCP/layout stability but increases transfer by 24,655 bytes
(3.94%) and delays DOM-ready/hydration. This is not an across-the-board speedup.
Navigation links work before hydration; demonstration controls require JS.
No authenticated data is prerendered; no request-time SSR server is introduced.

Artifact budgets are enforced by `corporate-release-audit.mjs`: initial JS
310,000 raw bytes; CSS 80,000; home HTML 40,000; WOFF2 inventory 102,000;
social PNG 500,000. Observed: JS 306,365, CSS 77,637, home 30,257, fonts
101,868 and social 448,345. These are regression budgets, not compressed-wire
or field metrics. Two critical fonts are preloaded only on public routes.

## SEO, social and identity

All 15 public routes have static unique title, description, canonical,
Open Graph and Twitter metadata and one H1. Sitemap coverage and private-route
exclusion are checked from emitted files. Unknown routes retain noindex and
must be served as HTTP 404, not a homepage success rewrite. Discovery MIME and
deep links are checked locally; live TLS/indexing remains deployment-owned.

The obsolete social card is removed from source and packaged output. It used
whitepact.dev and unqualified trust-badge imagery. The replacement retains the
WhitePact mark/wordmark and says “Independent authority before agent action”
with “For supported, configured execution paths” and whitepact.com. It is
1672x941 with matching metadata and accessible image description. Size falls
from 953,361 to 448,345 bytes (52.97%). Image generation is an illustration
workflow, not verification of a product security claim.

## Claims register

This register covers the meaningful assertion families in public content JSON,
HomePage, CorporatePages and shared trust/availability content. Repeated claims
inherit the same boundary; surrounding text and diagrams must retain it.

| Surface / assertion family | Classification | Evidence / required limitation |
| --- | --- | --- |
| Home: independently enforced authority before action; agent doctrine | Architecture description | Supported configured paths only; not protection against arbitrary same-process code or every agent |
| Home: illustrative deny/approval/allow scenarios | Architecture demonstration | Simulated, no live runtime result or external side effect |
| Home/product: governed API/MCP action boundary | Verified source-interface fact | Supported registered tools; deployed auth, consent and authority required; availability is separate |
| Product/architecture: identity, intent, authority, policy, risk, approval, judgment, grant, isolation, evidence, revocation | Architecture description | Conceptual chain, not proof every adapter calls every subsystem or every deployment isolates containers |
| Product/architecture: scoped/time-bound grants, fail-closed admission | Implemented control description | Exact baseline and configured path; UNKNOWN cannot be normalized into success or safely retried |
| Architecture/security: revocation | Implemented control description | Subsequent supported checks; no retroactive reversal of completed effects |
| Developers/docs: CLI, Python source HTTP helper, API/MCP examples | Verified source-interface fact | Pinned source baseline; role/tool/environment prerequisites, not a fictional stable SDK distribution |
| Security/trust: hash-chained evidence and verifier | Implemented control description | Tamper evidence with storage/verifier limits; not immutable against a compromised database; not external-effect proof |
| Security/trust: credentials, tenancy, deployment/TCB responsibilities | Architecture description | Backend authorization remains authoritative; browser, subscription and website are not authority |
| Trust: SOC 2/ISO 27001 and independent penetration testing | External-assurance statement | Not certified; commercial independent penetration test not claimed |
| Enterprise: private deployment and integration evaluation | Availability statement | Discuss scope/availability; no operational SLA or guaranteed deployment asserted |
| Enterprise: responsibilities/control checklist | Architecture description | Evaluation guidance, not certification or a signed enterprise contract |
| About: founder-led project and engineering history | Project fact | No invented staff, customers, funding, traction or corporate registration |
| Pricing: Community source / hosted / private evaluation options | Commercial/availability statement | Evaluation only; production billing/paid-service activation not established by this page |
| Contact: published project email and disclosure path | Availability statement | Actual mailto/repository links; not a staffed department, approved corporate identity or SLA |
| Sovereign: analysis, expectations and available contracts | Architecture/availability statement | Declared manifest input is not authority; canonical live output depends on deployed contract/session; unavailable stays unavailable |

No certification, zero-risk, universal non-bypassability, production-proven,
guaranteed-safe or paid-plan-derived authority is introduced. Owner legal and
commercial approval is not inferred from source or internal test success.

## Developer / package boundary

Examples remain pinned to product source baseline
`52d9b3c5497af24bb7d4a7147e33deaadc64296e`, not silently rewritten to a newer
unqualified runtime. `responsibleai` imports and `rai-governance-platform`
distribution naming are intentional current interfaces, not stray branding.
The documented published distribution check was 1.2.6 on 2026-10-04; website
1.3.1 manifest is not proof that a matching Python release is published.
Package identity/version alignment is a product-owner release gate, outside
website scope. No renaming or publication is performed.

Governed tools use POST `/api/v1/governance/tools/call`; Bearer evidence listing
uses GET `/api/governance/evidence`; browser evidence detail uses
`/api/web/evidence/EVIDENCE_ID` with session/membership. `/mcp` is the deployed
Streamable HTTP surface. The unavailable baseline SDK evidence-detail helper
is explicitly disclosed. Localhost setup URLs are intentional examples, not
production service claims. API documentation availability is deployment-owned.

## Security, privacy and dependencies

Exact future public-route headers, smoke checks and owner gates are in
`PHASE3_RELEASE_REQUIREMENTS.md`. The local browser server applies the restrictive
corporate CSP and rejects CSP/runtime console errors. No production header/TLS
claim follows. Authenticated Paddle/application CSP is not replaced.

Public-page requests, cookies and browser storage are regression-tested; this
is not an audit of authenticated processing, mail provider behavior or a future
edge/CDN. Analytics, third-party font services and embedded external media are
not added. No source maps or local developer paths should ship.

Website dependency correction: transitive development-tool `brace-expansion`
1.1.18 → 1.1.21 and 5.0.9 → 5.0.12. High recursion/DoS advisories
GHSA-qhr7-859c-m2p7/GHSA-6j4f-fj2g-mc7p and moderate
GHSA-q2hr-2g5m-vwhr concern crafted parser inputs, not a browser runtime parser.
They were remediated rather than dismissed. Fresh immutable npm installation
passes; npm audit reports zero advisories for this website lockfile. Audit is
time-sensitive and not a global security certification.

The existing ESLint-version support warning and deprecated whatwg-encoding
development dependency are recorded, not justification for unrelated major
dependency churn. Default-branch Python PyJWT/NLTK alerts are outside the static
website scope and remain for the product/security owner, not “false positives.”
CI actions remain immutable SHA-pinned; no action/coverage gate is weakened.
Website SBOM/provenance must be assessed against the final artifact by release
owners; Python wheel provenance is not automatically a standalone website SBOM.

## Release asset inventory and orphan handling

Deployment root: `src/responsibleai/dashboard/static/whitepact`.
Required: index shell; 15 public `pages/*.html`; separate private shell and 404;
robots.txt, sitemap.xml, llms.txt; favicon uses assets/whitepact-mark.png;
assets JS/CSS, seven WOFF2 files,
WhitePact mark/wordmark PNGs, wordmark WebP, trust-core-head.webp and current
social PNG. No approved security.txt is supplied yet. Do not deploy private
application routes with static public-page rewrites.

`corporate-release-audit.mjs` enumerates every emitted asset and byte size, route,
font and entrypoint budget. Lazy authenticated chunks remain shared build
artifacts, not public production functionality or authority. The old social PNG
is the only deliberately removed source asset; stale hashed JS is replaced by
the normal Vite build. The trust-core-head.webp remains referenced by the auth
chunk; PNG/WebP wordmarks are referenced by home, and the mark doubles as the
favicon. No guessed bulk cleanup occurs. Font inventory is unchanged.

Exact emitted asset filenames (under `assets/`):

```text
ApiKeysPage-BRPBmfyC.js
AuthPages-BczijCEy.js
CorporatePages-C9WgREwF.js
DashboardShell-CpLzvvRc.js
DomainPage-CnufVwrS.js
OnboardingPage-C5BDSMp-.js
OverviewPage-BBqBnjrq.js
PolicyPage-DtC541od.js
SovereignPage-DtYbl7WX.js
SovereignWorkbench-5tJBqLUL.js
api-heVFG2_0.js
building-2-BbSjWiFd.js
circle-question-mark-DYnd1y5Q.js
eye-CfCDSfsO.js
ibm-plex-mono-latin-400-normal-DMJ8VG8y.woff2
ibm-plex-mono-latin-500-normal-DSY6xOcd.woff2
index-qnjcdpgP.js
index-uwXgEc2w.css
jsx-runtime-hr28vSTc.js
key-round-DW9Tub0d.js
manrope-latin-400-normal-PaqtzbVb.woff2
manrope-latin-600-normal-4f0koTD-.woff2
manrope-latin-700-normal-BZp_XxE4.woff2
og-whitepact-phase3.png
plus-BdXyc8HD.js
rotate-cw-ipV-OxWS.js
scan-search-CSliL2tK.js
sora-latin-400-normal-CRt88UEn.woff2
sora-latin-500-normal-01eiPEn0.woff2
triangle-alert-D4FAyFfV.js
trust-core-head.webp
users-cvbh6xW4.js
whitepact-mark.png
whitepact-wordmark.png
whitepact-wordmark.webp
```

HTML: `index.html` plus `pages/home.html`, `product.html`, `architecture.html`,
`developers.html`, `docs.html`, `security.html`, `enterprise.html`, `trust.html`,
`about.html`, `contact.html`, `pricing.html`, `privacy.html`, `terms.html`,
`refund-policy.html`, `sovereign.html`, `not-found.html`, `private.html` (all under
`pages/`). Discovery: root `robots.txt`, `sitemap.xml`, `llms.txt`.

## Defects and external gates

| ID | Severity | State / boundary |
| --- | --- | --- |
| WP3-01 stale social domain/unqualified badges | P2 | Fixed in replacement social asset/metadata |
| WP3-02 static contact lacks actionable contact/disclosure | P2 | Fixed with existing published links, no invented corporate identity |
| WP3-03 homepage waits for JS; avoidable font-layout shift | P2 | Build-time home markup/preloads; measured tradeoff documented |
| WP3-04 script failure blanks other public routes | P2 | Fixed; all 15 routes passed blocked-script/asset regression |
| WP3-05 vulnerable build/lint transitive parser | P1 website toolchain | Patched compatible versions; fresh audit clean |
| WP3-06 production HTTPS/security/header delivery | External activation gate | Not deployed/verified in this phase |
| WP3-07 legal entity, jurisdiction, support/security contact | Owner input | Not invented; required before public activation |
| WP3-08 product distribution identity/runtime advisories | Product-owner gate | Not altered or declared resolved |
| WP3-09 exact-head CI and independent qualification | Engineering/qualification gate | Pending successor publication and independent review |

P0: none identified by local inspection; not an independent certification.
Unclosed checks and external gates remain explicit; a release verdict cannot
be inferred from local qualification alone.

## Local validation checkpoint

Lint, TypeScript/production build and 82/82 Vitest pass. Source-bound targeted
delivery/auth-boundary tests: 33 passed, zero failed. Browser: 150/150 axe scans
and responsive route layouts at 320/360/375/390/412/768/1024/1280/1440/1920;
15 no-JS routes; keyboard/disclosure/simulated-decision checks; reduced motion;
15 routes at 200% and 400% viewport equivalents and 200% text enlargement.
These equivalents are not a claim of OS-level zoom testing.

All 15 routes passed blocked JS/font/image testing at 320px. Delayed home JS
preserves the heading/docs link and successfully hydrates. Offline-after-load
content remains readable; this is not an offline/PWA cache claim. Clipboard
denial gives the manual-copy state without an unhandled rejection.
Restrictive CSP compatibility, HTTP 404, discovery documents, no external
public resource requests, no public API calls, no cookies and no storage writes
pass in the local static preview. Real production network/privacy behavior is
still a deployment smoke gate.

Static budgets/SEO audit, immutable-action pins, trust regression, documentation
consistency and tracked SPDX header checks pass. Sanitized artifact scan finds
no stale whitepact.dev/BiasBuster, local source paths, recognizable credential
material or public source maps. Intentional local development examples and
legacy supported package/import names are documented exceptions, not secrets.

Repeated builds of all 56 emitted files produced identical SHA-256 digests in
this environment. This is local website reproducibility proof, not a signed
release attestation or cross-platform bit-reproducibility claim. Commit-time
exact-head GitHub CI and independent Antigravity qualification remain pending.

Normative implementation references: [React hydration](https://react.dev/reference/react-dom/client/hydrateRoot),
[Vite build-time SSR facilities](https://vite.dev/guide/ssr.html),
[nested expansion advisory](https://github.com/advisories/GHSA-qhr7-859c-m2p7),
[comma parser advisory](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p).
