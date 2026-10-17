# First-passkey write-boundary correction — owner review required

M13 OPEN. GLOBAL PRODUCTION NO-GO. This proposal is not integrated into APEX.

Base: TITAN-1 2819be0938ac88c57dc9a7d0d1215c96d87b35ab,
tree781c18cc192a291786df7ea0565038698b9645cb. Existing owner branch unchanged.
Ownership requested: TITAN-1 independently review this security-owned correction.
No founder identity-assurance policy, root activation or session elevation changes.

## ABS-ENROLL-01

Confirmed P1 credential-write qualification violation, blocking first-passkey
acceptance. A genuine service password session, verified mailbox and real
ADD_PASSKEY grant precede a deterministically scheduled state change between
grant consumption and credential persistence. Unmodified owner source ignores
suspended organization, revoked membership/session, unverified mailbox and
absolute/idle expiration at the subsequent credential write.

Independent SQLite baseline:6FAIL/1PASS28.63s. Actual PostgreSQL baseline:
revoked-session and unverified-mailbox2FAIL27.26s. These use test-generated valid
WebAuthn registration bytes and actual persistence, not hardware attestation or
customer-journey success. No public HTTP exploit or root grant is claimed.

## Correction

- Hold user, organization, membership and session row locks through first-credential
  persistence, then recheck eligibility in that same transaction.
- Recheck canonical persisted absolute/idle expiry and authentication freshness;
  retain canonical created_at fallback for legacy null-auth_time password sessions.
- Propagate lock/read failures; remove the prior catch-and-ignore lock exception.
- Preserve challenge, UV, origin/RP, replay-marker and existing-factor checks.
- Registration alone leaves PASSWORD assurance and creates no root authority.

The original step-up grant is consumed before registration. A later qualification
failure denies persistence; it does not resurrect that one-time grant. Root
assurance remains a separate transition and Founder Record A remains unratified.

## Executed qualification

Initial stricter persisted-auth check denied legitimate null-auth_time sessions;
fixed before checkpointing to match canonical load_session fallback.
Correction plus unchanged identity-security neighbors:80PASS165.98s.
PostgreSQL scope:8PASS105.47s,7SQLite cases deselected, zero skips. Includes
one-winner concurrency with two independently valid challenges/grants, a barrier
after both real authorizations, actual row serialization and exactly one stored
credential/replay marker. All pre-existing reproducer files remain unchanged.

Genuine browser and final committed-head CI receipts are recorded in the review
PR. A passing owner proposal is not independent M13 acceptance. Remaining broader
session/policy races, account recovery, cross-account tenant rotation and owner
security contracts still require the responsible owner's qualification.
