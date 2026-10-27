# M13 integration handoff to Antigravity

## Branch

Work is on `cursor/m13-identity-trust-boundary-099e`, continued from PR #232 head `07be76a55913e1e201a281f3e316bd3c35929659`. Argon First Enrollment files and Codex recovery files were not modified. No merge was performed.

## Files

- `src/responsibleai/enterprise/verification.py` — session correlation, assurance policy, expiry, suspension, transitions, denial audit
- `src/responsibleai/enterprise/issuance.py` — expired verification cannot issue a key
- `src/responsibleai/enterprise/errors.py` — session, assurance, transition, conflict, and enrollment codes
- `src/responsibleai/enterprise/identity_provider_http.py` — fail-closed HTTP provider adapter
- `tests/identity_contract.py` — explicit non-production reference contract for existing software tests
- `tests/test_m13_identity_trust_boundary.py` — positive and negative boundary tests
- `tests/conftest.py` — restores identity-policy environment variables after each test
- Existing webhook callers that previously posted an unbound `VERIFIED` event now start a session and opt into the reference contract. The customer journey script was not given that opt-in.

## Tests

`tests/test_m13_identity_trust_boundary.py`: 10 passed, CPython 3.12.3, SQLite. Not run: CPython 3.11, PostgreSQL 16, Chromium customer journey, hosted CI.

Reviewer checks:

- A signed event whose `reference_id` belongs to user A and whose `subject_id` is user B must return `CROSS_TENANT` and leave both users unverified.
- With the approval environment variables unset, outcome `VERIFIED` returns `ASSURANCE_NOT_APPROVED`.
- `assurance_level` `sso` is rejected even when the reference contract is on.
- After `expires_at` is in the past, issuance reason is `IDENTITY_VERIFICATION_REQUIRED`.
- A `SUSPENDED` session rejects a later `VERIFIED` event with `VERIFICATION_TRANSITION_DENIED` and does not clear `revoked` on existing keys.
- Duplicate `event_id` returns `PROVIDER_REPLAY`.
- `HttpCallbackIdentityProvider.from_env()` with an empty environment returns `PROVIDER_NOT_ENROLLED`.

## Still blocked

- Founder choice of vendor, assurance token, and spend.
- Provider API token and webhook secret in the deployment environment, never in git.
- Historical DCO disposition, unchanged.
- Hosted I1 acceptance remains red until a real provider is enrolled. That is the intended gate.
- Independent adversarial qualification of this branch.

## Verdict

ENGINEERING IMPLEMENTED AND TESTED for the local software boundary.

INDEPENDENT REVIEW PENDING.

EXTERNAL PROVIDER AUTHORIZATION REQUIRED.

CANONICAL CUSTOMER JOURNEY BLOCKED.

M13 remains open. Production remains no-go. M14 is not authorized.
