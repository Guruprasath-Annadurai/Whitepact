# Browser acceptance matrix (campaign evidence)

**Environment:** LOCAL cloud agent (Chromium via Playwright customer journey; Vitest jsdom for route components).

| Route | Chromium | Firefox | WebKit | Desktop | Narrow | Mobile | Result | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Public marketing + auth shell | PASS | BLOCKED | BLOCKED | PASS | PARTIAL | PARTIAL | **PARTIAL** | Vitest + prior CI frontend closure |
| `/dashboard/*` (authenticated) | PASS | BLOCKED | BLOCKED | PASS | PARTIAL | PARTIAL | **PARTIAL** | Vitest dashboard flows; onboarding redirect added |
| Full multi-engine matrix | — | — | — | — | — | — | **BLOCKED** | Firefox/WebKit browsers not installed in agent VM |

**BLOCKED reason:** Cloud dev VM has Chromium (Playwright) only; Firefox/WebKit multi-engine sweep not executed this campaign.

**Determinism fix:** `tests/js/customer-journey.e2e.mjs` waits for identity-denial UI (≤8s) instead of fixed 500ms sleep.

**Classification:** Customer journey = **BROWSER TESTED** (Chromium, LOCAL). Full tri-engine matrix = **NOT YET PROVEN**.
