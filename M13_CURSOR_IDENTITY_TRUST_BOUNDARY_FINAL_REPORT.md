# M13 Cursor identity trust boundary

Baseline inspected: PR #232 head `07be76a55913e1e201a281f3e316bd3c35929659` (tree `d753171b97a6e3bb5135eb366f6c4b8f88bbe5e3`). That tree already refused reusable credentials with `IDENTITY_VERIFICATION_REQUIRED` unless `get_human_status()` reported `IDENTITY_VERIFIED`. The reference webhook could still write that status from a signed event that named a subject, without a pending session and without an approved assurance standard.

## What changed

`VerificationService.apply_provider_event` now accepts a human or organization outcome only when all of the following hold:

- The adapter verified the HMAC and the timestamp is inside 300 seconds.
- `event_type` is `identity.verification` or `identity.revocation`. A revocation event cannot use outcome `VERIFIED`.
- `event_id` is unique for the provider. A duplicate raises `PROVIDER_REPLAY` and does not change status.
- `reference_id` matches a session this deployment started for that provider. The client `subject_id` is compared with the session row. It is not used to choose a different account.
- An `org_id` on a human event must be an active membership of that session user.
- The current status is allowed to move to the new status. `SUSPENDED` does not return to `IDENTITY_VERIFIED` on the same session. `IDENTITY_VERIFIED` does not fall to `BASIC_VERIFIED`.
- `IDENTITY_VERIFIED` is written only when `identity_assurance_accepted()` is true.
- The session row is updated with a compare-and-swap on the previous status.

`get_human_status()` no longer treats a stored `IDENTITY_VERIFIED` row as effective when `expires_at` is missing or in the past (`EXPIRED`), when the user is `SUSPENDED`, or when the stored provider and assurance level are not currently approved. Email verification still projects `BASIC_VERIFIED` only. Credential issuance denies `EXPIRED` and `SUSPENDED` and still requires effective `IDENTITY_VERIFIED`.

Suspension updates `identity_verifications` and revokes keys whose `accountable_human_user_id` is that user. A later verification event on the suspended session cannot mint a new credential.

Denied provider events record `verification.denied` with the reason code, event id, and provider name. The raw body is not stored.

## Policy

`WHITEPACT_IDENTITY_APPROVED_PROVIDERS` and `WHITEPACT_IDENTITY_APPROVED_ASSURANCE_LEVELS` default to empty. Empty means no `IDENTITY_VERIFIED`. `hmac-reference` is ignored unless `WHITEPACT_IDENTITY_REFERENCE_CONTRACT=1`, and it is ignored whenever `is_production()` is true. Levels named email, SSO, passkey, sandbox, synthetic, or the reference adapter itself are rejected even if listed.

No founder assurance standard is recorded. The reference contract exists so software tests can exercise the state machine. It is not identity proofing.

## Tests run here

Command: `/tmp/wp/bin/python -m pytest tests/test_m13_identity_trust_boundary.py -q --tb=short -o addopts=`

Result: 10 passed, 0 failed, CPython 3.12.3, SQLite memory engine. PostgreSQL 16 and CPython 3.11 were not installed in this environment, so the concurrent case ran on SQLite transactions rather than PostgreSQL 16.

Covered: unknown session, subject substitution, missing policy, SSO assurance label, expiry, suspension, same-session resurrection denial, lower-assurance downgrade, replay, stale timestamp, missing reference, altered payload, revocation of an existing key, and fail-closed HTTP provider enrollment.

## Verdict

ENGINEERING IMPLEMENTED AND TESTED for the software trust boundary on CPython 3.12 and SQLite.

INDEPENDENT REVIEW PENDING.

EXTERNAL PROVIDER AUTHORIZATION REQUIRED before any production assurance claim.
