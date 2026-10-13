# Identity and Access — Live Staging Test Plan

SHA: `caf539b`

## Design (Phase 2)

| Requirement | Approach | Status |
|-------------|----------|--------|
| Phishing-resistant employee auth | Cloudflare Access + IdP WebAuthn/FIDO2 (no custom crypto) | **AWAITING_LIVE_STAGING** |
| JWT verification | `CloudflareAccessValidator` — iss, aud, JWKS, alg | **VERIFIED_AUTOMATED_TESTS** |
| No forged headers | `reject_unverified_identity_header` | **VERIFIED_AUTOMATED_TESTS** |
| Auth ≠ admin grant | Access JWT only proves identity; grants separate | **IMPLEMENTED** |
| Owner recovery | Separate break-glass IdP policy / allowlist | **OWNER_APPROVAL_REQUIRED** |

Verify Cloudflare plan supports: Access policies, session duration, revocation API — **BLOCKED_PROVIDER_ACCESS** until account review.

## Test cases

| ID | Scenario | Expected | Evidence type | Status |
|----|----------|----------|---------------|--------|
| I-01 | Legitimate owner WebAuthn login | Access JWT issued; app accepts | CF Access log + app audit | **AWAITING_LIVE_STAGING** |
| I-02 | Wrong credential | 401 at Access | CF event | **AWAITING_LIVE_STAGING** |
| I-03 | Expired session | `expired` / Access deny | JWT test + live | **VERIFIED_AUTOMATED_TESTS** (JWT); live **AWAITING** |
| I-04 | Forged JWT (wrong sig) | `jwt_invalid` / `bad_signature` | pytest | **VERIFIED_AUTOMATED_TESTS** |
| I-05 | Wrong issuer/audience | `issuer_mismatch` | pytest | **VERIFIED_AUTOMATED_TESTS** |
| I-06 | Forged `Cf-Access-Jwt-Assertion` header only | `header_not_trusted` | pytest | **VERIFIED_AUTOMATED_TESTS** |
| I-07 | Device posture (unsupported device) | Deny at Access | CF policy | **NOT_TESTED** — plan feature dependent |
| I-08 | Session revoke at IdP/Access | Subsequent API deny | Revocation API | **AWAITING_LIVE_STAGING** |
| I-09 | Authenticated user without grant | Cannot run privileged op | Executor disabled + grant verify | **VERIFIED_AUTOMATED_TESTS** |

## Execution notes

- Never paste recovery codes or private keys into chat or Git.
- Record JWKS URL, application AUD, and issuer in staging config store (not git).
- Map Access `sub` to `cloud_employees.employee_id` via documented enrollment step.

## Pass criteria

All **AWAITING** rows executed with captured logs/screenshots stored in owner-controlled evidence store (not public repo).
