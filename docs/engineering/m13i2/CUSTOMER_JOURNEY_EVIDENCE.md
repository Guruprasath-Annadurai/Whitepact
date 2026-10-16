# M13-I2 actual customer journey evidence

**Acceptance BLOCKED. GLOBAL PRODUCTION NO-GO.**

The reusable harness is `scripts/engineering/m13i2_customer_journey.py`; evidence-contract tests are `tests/test_m13i2_customer_journey.py`. The original I1 script is unchanged and its origin mismatch is preserved. This isolated branch started at `8cb692b99fb4b1fa894e07d432105209f430b0f7`, tree `6d00ded41d82feeb57b9f0842e000d9f4d22bd5f`.

## Actual run

Command: `PYTHONPATH=src:. /Users/ag/Whitepact/.venv/bin/python scripts/engineering/m13i2_customer_journey.py`.

The first actual run completed with exit **2**, correctly refusing to label the incomplete golden journey successful. It created/migrated a fresh disposable PostgreSQL database, used real loopback HTTP endpoints and a real local verification-email webhook receiver, and recorded 15 confirmed phases plus one blocked ceremony. The receiver accepts only the per-run delivery bearer secret. Development verification-token responses are disabled; the token used for verification comes exclusively from backend-generated mail received over HTTP. No external email was sent.

| Phase | Actual result |
| --- | --- |
| Fresh PostgreSQL migration | CONFIRMED |
| Unauthenticated session | 401 |
| Signup | 202; verification-required response without token/URL exposure |
| Backend-generated email verification | 200; verified acknowledgement |
| Password login | 200; actual session and CSRF cookies |
| First-run session | 200; matching account, no organization |
| Organization onboarding | 200; dashboard acknowledgement |
| Owner session | 200; backend OWNER membership and organization ID |
| Safe session reload | 200; same organization |
| Root status read | 200; backend reports no active authority |
| Agent inventory read | 200; actual empty registrations |
| Passkey registration begin | 200; genuine server challenge |
| Passkey registration finish | **BLOCKED**; configured origin mismatch and no real authenticator ceremony |
| Session logout | 200; signed-out acknowledgement |
| Session read after logout | 401 |
| Replay of the actually revoked session cookie | 401 |

Exact observed application origin: `http://localhost:58207`; server expected origin: `http://localhost`. Reason: `WEBAUTHN_CONFIGURED_ORIGIN_DIFFERS_FROM_APPLICATION_ORIGIN`. This is an actual HTTP application-origin versus challenge-contract observation; no browser authenticator assertion was performed, and no claim of full WebAuthn browser validation follows. The harness does not substitute the configured origin, manufacture WebAuthn data or invoke a fake authenticator. Challenge issuance is not a successful registration.

The final harness rerun, after adding semantic-exception preservation, again exited **2** with the same **15 confirmed / 1 blocked** phase results. Its exact application origin was `http://localhost:58471`, with server expected origin still `http://localhost`. Both revoked-session reads returned 401. No unexpected harness exception occurred.

Consent, root bootstrap, application creation, agent registration, delegation, policy mutation/enforcement, approval decisions, a controlled action, execution evidence and authority revocation/denial-after-authority-revocation were **not executed**. No root, passkey, consent, delegation or authenticated success was inserted in the database or mocked. Session revocation is not authority revocation. Local email capture does not establish external deliverability.

The server startup banner reports generic API auth disabled with an empty legacy static-key list. This harness does not claim legacy API authentication qualification: it directly confirms real browser-session protection with pre-login and post-revocation HTTP 401 responses, real account verification and OWNER membership. No legacy static key grants owner access.

## Reusability and failure evidence

Each recorded HTTP phase includes its actual/expected status and semantic-invariant confirmation. Successful HTTP alone cannot confirm owner membership, account state or a mutation acknowledgement. Failed semantic parsing retains earlier phases, appends a blocked phase and records the exception type without response bodies or exception text. Temporary application settings restore in `finally`; real servers and disposable databases clean up through context managers. The runner always emits acceptance BLOCKED and exit 2 because mandatory authority phases remain incomplete.

Focused tests check HTTP/semantic disagreement, preservation of prior phases after invalid JSON, absence of private response data, conservative partial acceptance and settings restoration after failure. These tests validate evidence handling only; they do not simulate authenticated authority.

Focused command: `PYTHONPATH=src:. /Users/ag/Whitepact/.venv/bin/python -m pytest -q --no-cov tests/test_m13i2_customer_journey.py`. Initial run: **4 passed in 4.37s** before the additional invalid-JSON preservation test. Final run: **5 passed in 5.11s**. Final Ruff check of both script and tests passed; `git diff --exit-code -- scripts/engineering/m13i1_customer_journey.py` also passed, preserving the original reproducer.

Loopback and disposable PostgreSQL execution required approved sandbox escalation. No deployment, cloud resource, external message, billing operation or security-owned source change was performed.

## Additional ordinary customer contracts

The harness also exercises the existing policy GET, pending human-approval dashboard read, bounded evidence GET and security-posture GET for the actual freshly verified owner. Empty policy/approval/evidence reads do not constitute configured policy enforcement, a human decision or evidence of an executed action. The `can_edit` display field is deliberately not interpreted as authorization to change policy.

Ordinary organization rename uses the existing CSRF-protected `PATCH /api/v1/web/organization`, whose backend requires owner/admin membership. The harness checks the exact `{id, name}` acknowledgement, reloads `/api/v1/web/dashboard/organization` from the organization repository, and reloads the authenticated session to confirm the same organization/name. This changes local disposable organization display metadata only; no authority ownership, membership or delegation is changed.

Actual extension run used the same documented CLI command against another freshly migrated disposable database and exited **2** with **22 confirmed phases and 1 blocked ceremony**. Policy visibility, pending human-approval status, bounded evidence list, security posture, organization rename, organization repository reload and renamed session reload all returned HTTP **200** with their semantic contracts confirmed. Actual policy/approval/evidence lists were empty; posture reported Passkeys NOT CONFIGURED. Application origin was exactly `http://localhost:59017`, server expected origin remained `http://localhost`, and the unchanged passkey stopping reason remained `WEBAUTHN_CONFIGURED_ORIGIN_DIFFERS_FROM_APPLICATION_ORIGIN`. Logout returned 200 and both post-revocation reads returned 401.

Final extension evidence-contract tests: **6 passed in 5.52s**, using the same pytest command above. Ruff passed for both files. The additional test confirms that policy/approval/evidence read visibility does not remove policy enforcement, approval decisions, execution evidence, authority revocation or denial-after-authority-revocation from the unexecuted matrix. No original I1 source or security-owned source was changed.

Parent independently reran the integrated extension: **6 tests passed in 6.95s**; actual fresh PostgreSQL/HTTP attempt again recorded **22 CONFIRMED / 1 BLOCKED**, exit 2. Observed origin `http://localhost:59198` versus configured `http://localhost`. This was an integration-source run while unrelated report edits continued; final exact-head CI is recorded separately.

Organization rename in this bounded HTTP run confirms only the ordinary current-session contract. It does **not** qualify concurrent workspace switching: the backend PATCH has no expected-organization/version precondition and acts on the current cookie principal. A later acknowledgement check cannot undo an unintended write after a cookie switch. The new product UI therefore leaves rename disabled pending a qualified backend contract; read-only organization metadata remains supported. No concurrency success is claimed.
