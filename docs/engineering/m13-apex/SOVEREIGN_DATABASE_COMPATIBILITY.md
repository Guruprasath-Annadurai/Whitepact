# Version-scoped PostgreSQL credential retirement — proposed operations contract

Status: disposable-test qualification only. NO production action performed.
This is a compatibility fence, not tenant isolation or a FORTRESS H1/H2 redesign.

## Selected smallest boundary

Use a distinct non-superuser runtime login per incompatible security generation,
separate from the migration/administrator identity. A historical0064 process must
not retain the0065 runtime credential. The current application's revision check
remains defense in depth; it cannot govern historical executables.

Before enabling mandatory0065 semantics, explicitly retire the legacy runtime
login (NOLOGIN), revoke its database CONNECT, and terminate its existing database
sessions through a separately authorized operator procedure. Keep migration
credentials out of all application environments. Do not grant old/new logins
membership in one another or leave an alternate shared administrative credential.
Role names in this document are descriptive, not actual production identities.

Connection-time application_name and user-set session variables are not authority:
old or misconfigured clients can forge them. Database constraints on selected
tables alone do not qualify all judgment/runtime side effects. A new generic
database trigger or broad RLS rewrite would add unrelated security architecture.
Version-scoped credentials plus actual retirement give a testable connection
boundary without pretending to patch immutable old binaries.

## Operator sequence — plan only, authorization still required

1. Inventory every deployed binary, pool, worker, runtime credential, database,
   role membership and privilege. Confirm there is no shared superuser or legacy
   fallback credential. Map the approved build to its compatible migration head.
2. Establish a maintenance/quiescence boundary. Disable new consequential
   admission and drain or contain old effects through existing qualified runtime
   procedures. Terminating a DB session alone does not terminate a Docker effect.
3. Create/inject the new version-scoped least-privilege runtime credential using
   existing approved secret handling. Do not put values in Git, CLI logs or report.
   Confirm current binary accepts the schema; migration identity remains separate.
4. Revoke legacy PUBLIC/inherited CONNECT paths as applicable, set the exact old
   login NOLOGIN, revoke its direct CONNECT, and explicitly terminate existing
   sessions for that login and target database. Require termination completion.
   Verify no alternate role, pool or reconnect path remains. Roll back uncommitted
   legacy transactions by confirmed session termination.
5. Apply approved security migration through its migration identity and locks;
   enable mandatory semantics only after legacy exclusion and runtime containment
   are independently verified. Start only the new runtime under its new credential.
6. Check startup compatibility, genuine authenticated customer operations,
   revocation, effect denial, logs and actual DB session identities. Preserve
   operator/build/schema/role identifiers and receipts, never password values.

No step above is performed against production by this work. Deployment and actual
credential retirement require separate infrastructure/operator authorization.

## Rollback, outage and restore

Failed preparation before activation: keep consequential admission disabled;
do not enable mandatory semantics until new runtime and exclusion qualify.
After mandatory rows exist, preserve0065 downgrade refusal. Never restore old
login access merely to make a historical binary boot. Use compatible corrected
binary or explicit reviewed recovery, not security-column deletion.

Connection outages must fail operations closed. Pools may not fall back to old
credentials. Restore cluster role state and database permissions together with
the compatibility manifest; a database-only backup is insufficient. Keep retired
logins NOLOGIN even if restore/regrant restores PUBLIC CONNECT. Revalidate all
roles, memberships, sessions, mandatory rows and execution containment before
reopening admission. No global backup/DR certification is claimed (FORTRESS H4).

## Disposable real-PostgreSQL evidence

`tests/test_m13_apex_database_role_retirement.py` creates only unique temporary
roles on a disposable DB. Demonstrates:

- Legacy credential can write before retirement; no claim a schema flag alone
  excludes it.
- CONNECT revocation alone leaves an already-open legacy transaction usable
  (negative control).
- NOLOGIN + CONNECT revocation + confirmed session termination blocks both fresh
  login and stale pooled connection; uncommitted write rolls back.
- New version credential remains usable, reconnects, and cannot SET ROLE legacy.
- PUBLIC CONNECT restoration does not resurrect a NOLOGIN legacy credential.
- Cleanup drops only test-created roles/grants and the disposable database.

This qualifies the proposed PostgreSQL connection boundary, not execution of the
historical application, production credential retirement, effect containment,
multi-region recovery or an approved rollout. Original0064/0065 migration and
dead-worker counterexamples remain unchanged and mandatory gates remain RED.
