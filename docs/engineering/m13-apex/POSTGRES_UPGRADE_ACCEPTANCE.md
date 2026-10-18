# PostgreSQL qualification — partial

Candidate40e43440489eebde6886af014943ea18ed228b68, tree
c6b106db0974838f084e391ca8f8b2f084c45882; PostgreSQL16.15 local disposable database.
No real customer data or reset; schema fixture rows are not customer authority.

Original unchanged18a upgrade counterexample PASSed c9a4436c applied0064 ->0065,
required column absent->present. Original historical migration tests2PASS on9fc.
Owner-authored PostgreSQL contracts independently executed6PASS on40e43440.

New separate `scripts/engineering/m13_apex_postgres_acceptance.py`:
0063->0064, insert two tenants and expired bootstrap plus recovery records,
then0065. Existing organization/bootstrap/recovery fields preserved exactly;
new required column non-null with default0 on both records. PASS.
Receipt `/private/tmp/apex-closure-pg-preservation.json`.

**APEX-PG-02: nonempty downgrade roundtrip BLOCKED.** Setting the new passkey
requirement to1, downgrading0065->0064 and upgrading again restores0 because the
downgrade drops the column. Ordinary records survive; security requirement does
not. This demonstrates destructive schema semantics, not an executed permission
bypass. Do not qualify nonempty rollback or infer it is supported. TITAN must
explicitly disposition rollback support and security-state restoration; Codex
has not edited the security migration or created a competing revision.

Clean installation is exercised by real customer/owner contract runs; broader
earlier revision support, concurrent application startup and startup mismatch
behavior still need independent qualification. No complete PostgreSQL acceptance
or production readiness is claimed.
