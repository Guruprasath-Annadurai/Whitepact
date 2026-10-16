# M13 controlled integration boundary

Global production NO-GO. No publication or deployment authorization is inferred.

## Provenance

- Product ancestor: `3592cfeaec946a38af20ca16ad38a54fb85c9454` (PR #205).
- Preserved six-file M12-FP signed-off commit:
  `3b8c001069d60a3fe4c0aa1d88b6e94318e41ef6`, tree
  `c986da57f563d60b1e5baa83e8ca6c58dcf95b63`.
- Explicit M13 security integration base:
  `4f383ffe069d6bec5f348ea934388e2a20b184a9`, tree
  `fed3210cff5c8b7c27006e8f672f4370f1386f66`.
- Product patch applied conflict-free as `c4eeb22b1ead09c01f443a6c438631e3ae007c22`.
  No security branch was blindly cherry-picked or overwritten. The security base
  already contains M12-P via merge `20764e00`; all security changes remain review
  inputs, not independently qualified fixes. No conflict resolution altered them.

## Ownership

Codex: frontend authority preparation, read-only recovery consumer, product acceptance
tests and evidence. Antigravity: security services, root/consent, WebAuthn verification,
quorum policy, runtime containment, schema and migrations. No Codex changes to those
surfaces. PRs #204/#205 remain preserved. Security fixes must return as exact reviewed
commits; re-run negative tests before enabling privileged navigation.

## Verified blockers

`tests/test_m13p_security_contract_acceptance.py` contains normal (not xfail) failing
tests proving omitted privileged step-up succeeds and termination failure is
unconditionally reported CONTAINED. It reuses isolated SQLite owner fixtures;
this is service failure proof, not a real customer journey.

`tests/test_m13p_postgres_schema.py` migrates a fresh isolated local PostgreSQL
database and proves all four new authority tables are missing after `upgrade head`.
No direct SQL root fixture is used. Metadata additions do not replace migrations.
The security owner must supply the ordered migration and downgrade contract.

Read-only recovery list uses actual session-authenticated GET routes, validates
tenant/address shape and projects allowlisted records. No mutation is sent, arbitrary
parameters are not copied, quorum is not calculated, unknown status is preserved,
and no production route imports these preparation modules.

Remaining security API drift, root assurance defaults, unbound consent fields,
caller-selected quorum, role rechecks, recovery scope expansion and token-in-URL
reconciliation must be reviewed by Antigravity. No browser adapter guesses endpoints
or changes security to make a happy path pass.
