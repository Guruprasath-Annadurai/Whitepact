# M13-P4 dashboard and enterprise UX

Status: product improvements prepared for review; **GLOBAL PRODUCTION NO-GO**.

## Changes

- Added a visible-on-focus skip link to a programmatically focusable workspace content target, without issuing a new session request.
- The mobile navigation opener exposes `aria-expanded` and `aria-controls`. The open drawer is a named modal dialog; its closed state is inert and hidden from assistive technology. The background content is inert while the mobile drawer is open.
- Existing Tab wrapping and Escape restoration remain in effect. The scrim is removed from sequential keyboard focus. Moving to desktop removes the mobile open state through a media-query listener.
- Expired sessions explain why sign in is needed. Forbidden sessions remain distinct from expired sessions; outages and malformed success remain unavailable, without presenting authenticated data.
- Logout requires the canonical backend acknowledgement. Uncertain results hide customer data and require session reload; no automatic mutation replay was introduced.

The drawer uses the same 820px breakpoint as the existing responsive stylesheet. Added the Agents navigation entry and lazy `/dashboard/agents` route after the inventory owner reported ordinary read-contract validation (owner empty read 200, unauthenticated 401, foreign tenant 403). Inventory details and summary/evidence changes are tracked in their respective reports. No privileged navigation was newly enabled by this UX work.

## Validation and limits

`m13p4-session-navigation.test.tsx` adds six component tests covering the new behavior, including keyboard Tab wrap/Escape, screen-reader semantics and inert attributes under a mobile media-query fixture. Existing session-policy and onboarding-accessibility tests are included in the focused run: **3 files, 15 tests passed**. TypeScript project checking also passed.

`tests/js/m13p4-accessibility.e2e.mjs` additionally ran Chromium **151.0.7922.34** against the real loopback app and rebuilt static assets using explicitly labeled browser session/read fixtures: **29 view/state checks, zero axe WCAG 2 A/AA and WCAG 2.1 AA violations, zero mutations**, at 375, 768 and 1280px. `tests/test_m13p4_browser_accessibility.py` creates and migrates a disposable PostgreSQL database, starts the real app, runs the browser script and cleans up. This checks public signup/login/onboarding, read-only dashboard/agent inventory, mobile drawer, expired and forbidden sessions; it asserts no viewport overflow, keyboard skip navigation, native inert/focus behavior, Tab wrapping and Escape restoration. This is **not customer authentication or authority acceptance**. External origins are aborted and all API mutations are blocked by the test harness. It does not exercise a screen reader application.

The final coverage extension adds `/dashboard/agents` with 11 non-secret registration fixtures returned from `/api/enterprise/organizations/fixture-org/authority/agents`: a long identifier, `UNKNOWN_FUTURE` lifecycle, and a reported active delegation that is explicitly not execution authority. At every viewport the browser audits the loaded view, a no-match filter and the second local page; it asserts absence of registration/delegation/disablement/execution/authorization/grant/revocation buttons. The complete fixture suite now contains **29 checks**. The application and agent read tests remain separate from independent privileged security acceptance.

Final extended-suite command: `PYTHONPATH=src PLAYWRIGHT_BROWSERS_PATH=/Users/ag/Library/Caches/ms-playwright /Users/ag/Whitepact/.venv/bin/python -m pytest -q tests/test_m13p4_browser_accessibility.py`. Result: **1 passed, 1 warning in 88.96s**; the warning is the same deprecated non-production test-key fixture described below. No product source change or rebuild was required for this coverage extension.

Final command: `PYTHONPATH=src PLAYWRIGHT_BROWSERS_PATH=/Users/ag/Library/Caches/ms-playwright /Users/ag/Whitepact/.venv/bin/python -m pytest -q -s tests/test_m12p_live_public_browser.py tests/test_m13p4_browser_accessibility.py`. Result: **2 passed, 2 warnings in 166.60s**. Both warnings report deprecated legacy static API keys in the non-production development test fixture; no production key or owner authority is seeded. The existing public/unauthenticated suite independently passed its 16 real app/PostgreSQL browser checks at 375, 768, 1024 and 1440px, including actual HTTP 401 session reads and unavailable private evidence. The new suite passed its 20 labeled UI fixture checks, with compiled font assets returning HTTP 200.

Executable: `/Users/ag/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell`. Initial sandbox attempts failed with loopback `listen EPERM` and Chromium Mach bootstrap permission denial; approved local launches ran successfully. An exploratory Vite run also passed 20 checks but denied symlinked font files; the final compiled-static run removes that limitation. `ruff check tests/test_m13p4_browser_accessibility.py` passed.

A focused component test initially selected the loading status too early; the corrected wait targets the final explanation. Record the final integrated command/result in `WHITEPACT_M13P4_TEST_AND_CI_MATRIX.md`.

## Unresolved qualification boundaries

Passkey, explicit privileged consent, root authority, quorum and sensitive customer actions remain **BLOCKED** until independent acceptance on the reviewed unified commit. UNKNOWN/UNRESOLVED outcomes must remain visible as uncertain; these UI changes do not clear existing findings or establish authority.
