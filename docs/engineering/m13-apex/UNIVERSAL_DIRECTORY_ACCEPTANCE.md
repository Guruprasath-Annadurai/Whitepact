# Directory acceptance — partial

APEX-DIR-01 metadata projections repaired at8170a5fd. APEX-DIR-02 rejects empty
canonical claims, multiple-at-sign email, empty extracted domain and invalid
digitless/overlength phone. Five regressions failed before the repair.

Expanded directory/receipt run:20PASS, zero skips,47.71seconds. Both SQLite and
actual migrated PostgreSQL execute metadata, concurrent claims, Unicode/IDNA
email resolution, cross-tenant delete denial, tombstone invalidation and
identifier recycling. A replacement gets a distinct principal, empty metadata,
PENDING_VERIFICATION lifecycle and UNVERIFIED binding. Descriptive metadata is
never interpreted as authorization. Existing original directory tests preserved.
This checks repository invariants, not a complete customer-authority journey.

Canonical directory consumers found in source are
`src/responsibleai/trust_fabric/decision.py` and `passport.py`; neither reads
descriptive metadata for permission. No direct dashboard/router call to
PrincipalDirectory was found. Thus UI application/agent records must not be
claimed as proven canonical-directory integration. Application/agent principal
relationship and revocation-propagation acceptance remain open; require the
TITAN authority identity contract before connecting privileged relationships.

Normalization is not a complete email/phone/domain verification service.
Passing malformed-input checks does not establish ownership of an identifier.
