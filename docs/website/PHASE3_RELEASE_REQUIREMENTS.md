# Phase 3 website release requirements

Engineering preparation only. No deployment, DNS, Cloudflare, billing or package
publication is authorized. Phase 2 remains frozen at
`1634c542e49039828e1913c9f01ff63bb4be1de2`.

## Delivery and security boundary

Serve immutable built assets from `src/responsibleai/dashboard/static/whitepact`.
The application delivery tests remain the authority for its public route/status
mapping. Static hosting must map each public URL to its corresponding
`pages/*.html`, not universally return the homepage. Unknown URLs must return
`pages/not-found.html` with HTTP 404. Never serve private application data through
a static rewrite. Authenticated console/API routes are separate product surfaces.

Suggested **corporate public-route** CSP (not a replacement for the authenticated
application's reviewed Paddle policy):

```text
default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'
```

No `unsafe-inline`, `unsafe-eval`, script wildcard or third-party connection
exception is proposed. JSON-LD is inert structured data, not executable script.
The browser suite must demonstrate compatibility and reject console/CSP errors.
External GitHub/mailto destinations are user-initiated links, not embedded
resources. Current application headers allow additional Paddle origins for the
customer application; this document does not alter those headers or billing.

Also require `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: strict-origin-when-cross-origin` and
`Permissions-Policy: camera=(), microphone=(), geolocation=()`.
HSTS is a deployment decision after valid HTTPS and all affected subdomains are
verified: begin with a short max-age, then approve a longer lifetime. Do not
request HSTS preload or `includeSubDomains` without owner review of every host.
Do not send production secure-cookie claims based on localhost tests.

Corporate navigation must not create cookies, localStorage/sessionStorage,
analytics, pixels, beacons, remote fonts or embedded third-party media. Login,
email inquiry and authenticated workspaces have separate data-processing
boundaries. No marketing analytics are added.

## Future production smoke specification

Run only after deployment authority is granted, against the exact approved
artifact and intended HTTPS hostname. This phase runs local checks only.

1. Verify TLS chain, hostname and expiry; HTTP-to-HTTPS redirect without loops.
2. GET and HEAD all 15 public routes: HTTP 200, correct unique title,
   description, canonical, social metadata and one H1. Refresh deep links.
3. Unknown route: HTTP 404, readable return-home action, noindex, no home
   canonical. `/refunds` redirects to `/refund-policy` without duplicate indexing.
4. Verify reviewed headers above on HTML/assets and no mixed content/CSP errors.
5. Load every referenced JS/CSS/font/logo/favicon/social asset; verify status,
   MIME, immutable content hash and absence of source maps/secrets.
6. GET `/robots.txt`, `/sitemap.xml`, `/llms.txt`: correct MIME, canonical host,
   public route coverage, private-route exclusions and no private tenant URLs.
7. Test keyboard navigation, mobile menu, disclosure, clipboard fallback and
   simulated decision dialog; no effect-producing request from the public demo.
8. Check no-JS and delayed-JS homepage readability, 320px reflow, 200/400% viewport
   equivalents, reduced motion, blocked fonts/images and connection interruption.
9. Inspect request destinations, cookies and browser storage before and after
   corporate navigation. Authenticated product APIs must still reject anonymous
   callers; public HTML availability does not authorize product operations.
10. Verify contact mailto/disclosure/GitHub/docs destinations. A contact link is
    not a staffed service/SLA. Confirm legal/commercial owner inputs before launch.
11. Measure fresh lab performance; establish field monitoring separately. Local
    LCP and layout-shift measurements are not field CWV/INP or uptime proof.

## Owner inputs required before public activation

| Input | Current truthful boundary |
| --- | --- |
| Legal operator/entity, registration, address, jurisdiction, tax identity | Not inferred or fabricated; legal approval remains owner-controlled |
| Corporate support/sales contact and staffed-service commitments | Existing published project email only; no support SLA is represented |
| Security contact and security.txt expiry/canonical approval | Repository disclosure link exists; new security.txt waits for approved contact/expiry |
| Processing providers, locations, retention periods and policy effective date | Require actual operational inventory and counsel/owner review |
| Commercial plans, paid availability, billing activation and contract terms | Evaluation copy does not establish an active subscription or entitlement |
| Production URL/delivery identity, TLS, header and availability validation | No deployment proof is created in this phase |
| External certification/penetration test status | No certification or commercial independent penetration test is claimed |

## Supply-chain / advisory boundary

Website lockfile fixes only confirmed compatible development-tool transitive
`brace-expansion` versions: 1.1.18 → 1.1.21 and 5.0.9 → 5.0.12. Relevant advisories:
GHSA-q2hr-2g5m-vwhr, GHSA-qhr7-859c-m2p7 and GHSA-6j4f-fj2g-mc7p. These parsers are
not shipped in the production browser bundle; crafted build/lint inputs remain a
toolchain DoS risk, hence remediation rather than dismissal. Lockfile root version
is aligned with the pre-existing 1.3.1 manifest; no product release is published.

GitHub default-branch PyJWT/NLTK alerts concern Python runtime dependencies, not
the static corporate browser artifact. They are **not declared false positives
or resolved**. Product/security owner must assess them before product release;
website work does not modify Python, authorization, package publishing or runtime.
No global "security clean" claim follows from a clean website npm audit.

Reproducibility, SBOM and provenance must refer to the final exact artifact, not
an earlier candidate. Source and lockfile integrity plus exact-head CI are the
engineering gate; independent qualification remains Antigravity's responsibility.
