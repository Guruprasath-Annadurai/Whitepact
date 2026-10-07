# External website acceptance — prepared, not deployed

This Track C tooling does not deploy, change DNS or mutate an origin. The frozen Phase 4 candidate is unchanged. It requires explicit target, profile and expected canonical origin. External invocation additionally requires `--authorize-external`. No default production URL exists. Reports are machine-readable JSON; `UNVERIFIED` is never PASS and exit status is nonzero until every check passes.

```sh
BASE_URL=https://staging.whitepact.com SITE_PROFILE=staging EXPECTED_SITE_ORIGIN=https://staging.whitepact.com node web/tooling/acceptance/run.mjs --authorize-external
```

Run only after the owner authorizes that target. This command is documentation, not evidence it has run. External link HEAD requests require separate `--authorize-link-targets`; redirects are not followed. Browser requests to unrelated origins are blocked. Certificate validation is never disabled. Reports suppress exception/body/credential values.

Optional explicit evidence inputs:

- `SECURITY_CONTACT_CONTRACT`: owner-approved JSON containing `contact`, UTC RFC3339 `expires`, and `ownerApproved:true`; without it security.txt remains UNVERIFIED.
- `MAINTENANCE_PATH`: operator-provided safe read-only path currently serving maintenance. Checks HTTP 503, no-store and Retry-After. The harness cannot switch maintenance mode.
- `ROLLBACK_MANIFEST`: prior released artifact manifest. Retained asset bytes are compared; actual activation/rollback rehearsal still needs operator evidence. No rollback is performed.
- `ROLLBACK_PATH`: explicit same-origin read-only rehearsal path currently serving the previous homepage. Together with the prior manifest, checks prior HTML bytes and all retained prior asset hashes. This does not prove the operator's activation mechanism or perform activation.

Browser checks exercise every public route at 375/768/1024/1440 in normal mode; CSS zoom 200% at 320/360/375/390/412/768/1024/1280/1440; and 375/1440 in no-JS, blocked-assets, reduced-motion, slow-network and offline-after-load modes. This is 345 traversals for the current 15-route inventory. Zoom checks inspect page overflow and clipped interactive targets. CSS zoom is not a substitute for every browser's native UI zoom. Slow network uses Chromium CDP: 150ms latency, 200000 bytes/sec download and 93750 bytes/sec upload; API failure prevents acceptance. Keyboard checks prove focus, mobile menu Enter/open/Tab/Escape/restoration and Tab/Enter activation of an actual internal route with resulting URL and heading assertion, not complete screen-reader qualification. Reduced-motion checks inspect running animation durations as well as media preference. LCP/CLS thresholds are laboratory only; INP and field CWV remain unverified. The harness intentionally reports remaining limitations rather than promoting these probes to universal assurance.

HTTP checks reuse Phase 4 strict smoke plus structured-data parsing, discovered link checks, asset fingerprint/cache validation, adjacent source-map probes and credential-signature scans. Such scans cannot prove absence of every secret or unreferenced resource. An origin or WAF failure causes nonacceptance, not a fabricated empty success.

## Requirement-to-probe matrix

| Requirement | Implemented probe | Local evidence / future boundary |
|---|---|---|
| HTTPS, TLS | Explicit HTTPS, default CA/hostname verification, TLS >=1.2 socket | Configuration rejection unit tests; future TLS host unverified |
| Redirects | Manual refund redirect and HTTP-to-HTTPS canonical redirect | Local refund fixture; external redirect future |
| Headers/CSP/HSTS | Exact Phase 4 public header contract | Local header fixture; HSTS never claimed on HTTP |
| Canonical/robots/sitemap/llms | All 15 routes/discovery profile checks | Real frozen artifact HTTP fixture |
| Structured data | Every route requires nonempty parseable schema.org JSON-LD with type | Real artifact fixture |
| security.txt | Owner-approved contact/expiry compared at well-known path | No owner approval; UNVERIFIED |
| 404/routes | Status/readable heading and exact public inventory | Real fixture |
| No-JS/blocked-assets | Every route meaningful heading/title without scripts/assets | Local browser optional test mode |
| Asset version/cache | All artifact-manifest assets compared byte-for-byte; immutable hashed assets | Real fixture, includes lazy chunks |
| Source-map/secret leakage | All manifest JS/CSS + HTML scanned; adjacent maps probed | Real fixture; pattern-based not universal proof |
| Accessibility/keyboard | axe, actual focus + link activation/navigation | Local browser optional test mode |
| Widths/zoom | Four widths; CSS zoom 200% and overflow | Reflow approximation, native browser zoom still separate |
| Reduced motion | Media preference and actual running animations <=10ms | Local browser mode |
| Slow network/offline | Chromium CDP latency/download/upload throttling; offline after successful load | Chromium laboratory emulation, not a real carrier |
| Lab CWV | Observed per-route LCP/CLS thresholds | Not INP or field measurements |
| Internal links | Discovered same-origin routes GET checked | Real fixture |
| External/GitHub/docs | Explicit separately authorized HEAD; 3xx remains UNVERIFIED | No external requests executed |
| Maintenance | Explicit path 503/no-store/Retry-After | Future operator-provided path |
| Rollback | Explicit prior manifest + prior homepage response/hash | Future rehearsal path; no activation mutation |

Track C is PARTIAL for full native browser zoom and future external acceptance. Laboratory INP and full assistive-technology qualification are not claimed; field INP is outside laboratory CWV checks. These boundaries are not concealed by the implemented browser probes.

## Finalization scope

The historical Track C failure evidence below is retained rather than erased. The finalization program fixes CSS reflow at its public-page causes, expands the CSS-200% matrix to nine widths, and records final results in `WHITEPACT_PUBLIC_PRODUCT_FINAL_REPORT.md` at the worktree root. Native browser/OS zoom, manual assistive-technology certification and live external acceptance are not promoted from these laboratory checks. `result.httpFailures` contains the strict HTTP smoke's route-specific status/header/indexing/asset diagnostics; private response bodies are not included. Future acceptance still exits nonzero when any required live check is UNVERIFIED.

Local unit validation:

```sh
node --test tests/js/website-external-acceptance.test.mjs
```

No external target was contacted during implementation. Deployment, trusted DNS/edge topology, certificate renewal, origin protection, owner-approved security contact and real rollback rehearsal remain external gates.

## Historical pre-finalization evidence and retained failure

The results below describe the earlier Track C checkpoint, not the final successor. They are retained to disclose failed runs. Fresh full-matrix successor results supersede their current-status statements; native browser zoom and live external acceptance remain separate gates.

Build the existing locked frontend first so `public-routes.json` is generated. Browser validation uses existing root Playwright dependencies. `RUN_ACCEPTANCE_BROWSER=1` runs the complete 345 traversal matrix; `ACCEPTANCE_FOCUS=1` limits browser traversal to the homepage for diagnosis, not whole-site qualification. The standalone CLI always uses the full generated public inventory. Normal browser traversal contributes hydrated links to the HTTP link checks; HTTP-only mode covers static HTML links only. The documented protected `/api/docs` reference may legitimately require authentication (401/403), which is not treated as a nonexistent endpoint. TLS probes use the explicit target port and retain hostname/certificate verification.

- Frozen source base remains `c9622a2539f20314205e1c30a0f4b8de3927b8f4`; no commit, push or deployment performed.
- Locked production build passed and left tracked artifacts unchanged.
- Final unit + real localhost HTTP artifact fixture: **10 passed, 0 failed**, exit 0. Includes invalid target/profile/credential origins, non-HTTP canonical origins, origin mismatch, nonpass UNVERIFIED behavior and actual asset/cache/link/source-map checks.
- Initial full 240 traversal browser matrix completed, but **8 passed, 1 failed**, exit 1: mobile aggregate incorrectly included CSS-disabled and CSS-zoom layouts. This is retained as a failed run, not promoted to a pass for changed code.
- Diagnostic homepage run identified overflow at `/`, width 375, in blocked-assets and CSS zoom 200% modes. CSS-disabled layout is now recorded separately, not attributed to ordinary styled mobile layout. The degraded observation is preserved.
- Final current-code focused browser run: **9 passed, 1 failed**, exit 1. Remaining failure is `zoom-200`, homepage `/`, 375px. Ordinary mobile widths, no-JS, blocked-assets meaningful content, axe, actual keyboard navigation/menu behavior, reduced motion, CDP slow network, offline-after-load and lab LCP/CLS probes passed within this focused homepage scope.
- CSS zoom 200% at 375px is a reflow approximation (approximately 187.5 CSS-pixel effective width), not independent native browser zoom proof. Failure is not suppressed; no product defect conclusion or product fix is made.
- No fresh full-matrix PASS exists for the final harness. Track C remains **PARTIAL** pending full current-code browser qualification and native zoom adjudication. External host, owner-contact, maintenance and rollback acceptance remains UNVERIFIED.

## Website-completion browser execution

The historical results above remain historical; they must not be substituted for a fresh result on a successor website head. The corporate browser suite now supports an explicit engine/channel and serves a private snapshot of the built artifact, preventing a concurrent rebuild from replacing files underneath its HTTP fixture.

```sh
npm --prefix web run build
WHITEPACT_WEBSITE_BROWSER=chrome npm run test:corporate-website
WHITEPACT_WEBSITE_BROWSER=firefox npm run test:corporate-website
WHITEPACT_WEBSITE_BROWSER=webkit npm run test:corporate-website
```

The default is `chromium`; `msedge` is supported only when that channel is installed. Missing browser executables are failures, not silently substituted engines. Record browser name/version with each result. Playwright WebKit is engine-level evidence, **not** a claim that native Safari or iOS Safari was tested. Native Safari, native zoom and assistive-technology checks remain separately identified evidence.

The responsive matrix includes 320, 360, 375, 390, 412, 430, 768, 1024, 1280, 1440, 1728 and 1920 CSS pixels. The suite also checks mobile disclosure dismissal, keyboard navigation and browser back/forward. Optional `WHITEPACT_WEBSITE_SCREENSHOTS` must be an absolute directory outside the repository; screenshots are named by browser, route and width. Never claim a final pass from an interrupted run or one that traversed different artifact generations.
## Public navigation pointer/scroll regression

The global smooth document scroll could continue after activating the skip
link. In Firefox 153.0 on macOS 27.0.1, a subsequent 120 ms menu press was
observed with `pointerdown` on the toggle at scrollY 36, followed by
`pointerup` on the hero at scrollY 77. The resulting `click` targeted their
ancestor rather than the button, so the menu's click handler never ran.
This is not an authority, API, or hydration failure.

The focused comparison reproduced one failure in ten smooth-scroll presses
and zero in ten instant-scroll presses; a separate instant-scroll sequence
also completed thirty presses without failure. Those observations identify
the mechanism, not a statistical reliability guarantee. The public document
now uses standards-based `scroll-behavior: auto`, scoped to the corporate and
Sovereign public shells. Console/auth behavior is unchanged. A redundant
14 px button font rule was removed (the shared button already defines it) to
keep the existing initial CSS budget intact.

The browser gate checks computed public scroll behavior and performs a
120 ms press immediately after skip-link focus at every mobile route/width.
Do not mask this regression with forced clicks, sleeps, browser-specific
user-agent branches, or test retries. Native Safari observations and
Playwright WebKit results must continue to be reported separately.
