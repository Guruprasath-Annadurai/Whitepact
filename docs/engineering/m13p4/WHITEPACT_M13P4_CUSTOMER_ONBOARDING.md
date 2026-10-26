# M13-P4 customer onboarding preparation

Production status: **GLOBAL NO-GO**. Product UI validation is not independent security acceptance.

## Supported product portions

The existing signup, email verification, password login/recovery and three-step onboarding use real `/api/v1/web/` endpoints. Onboarding retains a validated session-only draft, moves focus to the current step heading, names its choice groups, and accepts creation only after the backend returns `next: /dashboard`. A plan choice records a preference; it does not activate billing or authority. No mocked success was added.

`GET /api/v1/web/session` is the canonical shell read. Its backend returns the user, active organization and membership list. The shell re-verifies on route changes, aborts obsolete reads and prevents late reads from mounting old route content. Malformed success, forbidden access and availability failures hide workspace content; only HTTP 401 leads to sign in. M13-P4 adds an accessible explanation on that sign-in journey and uses history replacement so back navigation does not reopen the expired route.

Sign out uses the existing CSRF-protected POST contract. The backend returns `status: signed_out` after session revocation and clears the session/CSRF cookies. M13-P4 requires that acknowledgement before navigating to the signed-out destination. A disconnect or malformed success leaves the effect uncertain, hides workspace data and offers a full session reload without replaying the POST. No client-side cookie manipulation substitutes for backend revocation.

## Preparation and qualification gates

| Journey | Current product disposition | Required evidence before enablement |
| --- | --- | --- |
| Signup, email verification, login and first-run form | Existing real endpoint integration; frontend regressions applicable | Real PostgreSQL and backend tests recorded separately by the integration owner |
| Organization selection | Session membership/active-organization information exists; no new switch control enabled | Independent review of session switching, membership authorization and CSRF contracts |
| Passkey registration | **BLOCKED**, preparation only; no new registration controls | Reviewed WebAuthn origin, challenge, replay and identity-binding results on the unified commit |
| Explicit action consent | **BLOCKED**, preparation only | Reviewed durable consent scope, challenge freshness and identity binding; terms acceptance is not execution consent |
| Root bootstrap/recovery | **BLOCKED**, preparation only | Independent quorum/concurrency/crash acceptance and original reproducer passes on the unified commit |
| Application/agent execution | **BLOCKED** pending independent security qualification | Inventory registration/read access must not be interpreted as execution authority |

The supported session endpoints were inspected in `src/responsibleai/dashboard/app.py`; no security-owned implementation was changed. This work does not claim browser-level or backend qualification from component mocks.

## Focused verification

Command (web directory): `npm test -- --maxWorkers=1 src/test/m13p4-session-navigation.test.tsx src/test/m11-session-policy.test.tsx src/test/m13p-onboarding-accessibility.test.tsx`.

Result: **3 files, 15 tests passed**. `npm exec tsc -- -b --pretty false` also passed. The new coverage checks 401 explanation, uncertain sign-out outcomes, canonical successful sign out, skip navigation, and mobile keyboard/focus isolation. The first run exposed a test wait that matched the initial loading status before navigation; the assertion was corrected to wait for the exact expired-session explanation. No product failure was suppressed.

See the final test/CI matrix for the final integrated result and exact candidate identifiers.

Browser follow-up: the real app with migrated disposable PostgreSQL passed the existing 16 public/unauthenticated checks. A separate compiled-static Chromium 151.0.7922.34 accessibility suite passed 29 checks at 375, 768 and 1280px with no axe WCAG A/AA violations or overflow. Public signup/login/onboarding were rendered by the actual app; dashboard, read-only agent inventory and expired/forbidden-session behavior used explicitly labeled browser response fixtures with all mutations blocked. The final inventory coverage run passed in 88.96s with one deprecated development test-key warning. This does not verify signup completion, a real authenticated customer or privileged authority. Exact command, browser executable and environmental retries are recorded in the enterprise UX report.
