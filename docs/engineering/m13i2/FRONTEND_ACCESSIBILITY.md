# M13-I2 frontend accessibility and uncertainty validation

Scope: read-only Agents inventory and the on-demand root/consent record-status panel. GLOBAL PRODUCTION NO-GO.

## Observable behavior

- Semantic labeled sections expose inventory and record-status boundaries. A pending read sets `aria-busy`; loading/results use polite status announcements, and failures use an alert.
- Inventory failures produce a single alert containing the specific session/access/unavailable explanation and the unchanged no-success/no-empty statement. The previous duplicate alert is removed.
- Read, refresh and retry use native buttons. Pending reads disable repeat submission. Keyboard Tab/Enter operates the first status-read button. Missing organization context presents an unavailable explanation and dispatches no read.
- A 401 status response offers a normal sign-in link returning to Agents. Other failures do not claim that the session expired.
- Record IDs wrap and remain literal backend-returned identifiers. No color-only success/permission signal or enabled privileged action is introduced.
- Refresh and tenant transitions remove prior record data immediately. Late responses cannot replace another tenant's view. A previous successful read cannot remain visible as current truth after a failed refresh.

## Regression evidence

`web/src/test/m13i2-authority-record-status.test.tsx` exercises keyboard operation and GET shape, reported active/inactive record pairs, 401/403/503 handling, explicit retry, lost refresh acknowledgement, cross-tenant payload rejection, slow read busy state, cancellation and ignored late tenant response, shared API timeout, and missing organization context. `m13p4-inventory-page.test.tsx` adds successful-inventory refresh followed by lost response, asserting stale data removal and exactly one alert.

Component tests use controlled HTTP responses to exercise real consumer validation and browser request lifecycle. They do not prove backend authorization or a completed actual customer authority journey. The retained reader tests cover malformed records, identifier validation, error propagation and unexpected-field exclusion.

Fresh isolated-branch validation: `cd web && npm test -- --maxWorkers=1` — **30 files / 275 tests passed**; `npm run lint`, `npx tsc -b --pretty false`, and `npm run build` — **passed**. The generated static bundle is retained with the source change. `git diff --check` passed.

`tests/js/m13i2-accessibility.e2e.mjs` plus `tests/test_m13i2_browser_accessibility.py` add **21 planned browser checks**: seven panel states at 375/768/1280 widths, real compiled static UI, explicit session/API fixtures, keyboard Enter, axe WCAG A/AA scans, overflow checks, slow-read busy state, failed refresh/retry, long record identifiers, foreign payload rejection and session-expiry sign-in. It rejects non-GET API traffic and asserts zero mutations. JavaScript syntax check and Python Ruff lint/format checks passed. The parent runs this browser wrapper against the unified exact-head bundle; it is not reported as executed here. Existing 29-check P4 browser suite remains unchanged.

Automated DOM/keyboard assertions are bounded evidence, not a full WCAG conformance claim. This worker did not perform a real screen-reader session or browser zoom/contrast audit; exact-head browser and integrated customer journey validation remain parent acceptance tasks.
