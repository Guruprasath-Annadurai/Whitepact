# Phase 10 — Rollback and incident playbook

**Not exercised on production. Production does not have a release from this branch.**

## Emergency stop

1. Stop issuing new execution grants. Do this in the authority service, not by telling the agent to refuse.
2. Revoke active grants for the affected tenant, or for every tenant if the defect is a bypass.
3. Keep evidence append-only. Do not delete audit rows to "clean up" an incident.
4. Shift traffic to the last pinned SHA only if that SHA is not the source of the bypass. If the bypass exists in both, stay stopped.
5. Tell the owner. Do not post a public incident until the owner approves the text.

## Rollback

| Situation | Action |
|-----------|--------|
| Bad staging apply, no customer data | Owner approves destroy or redeploy of the previous SHA |
| Bad application SHA, database compatible | Redeploy previous digest. Do not run a down-migration unless the owner and the migration author agree |
| Bad migration | Restore the scratch-tested backup into a new database. Point the app only after the digest check |
| Suspected authority bypass | Stop grants first, then roll back. A rolled-back process that still honors stolen grants is not contained |
| Payment webhook storm | Reject at the signature check. Do not disable signature verification |

## Severity

Use the table in `PHASE_06_RELIABILITY_AND_RECOVERY_PLAN.md`. Severity 1 includes memory-scope widening, cross-tenant reads, and grant replay that succeeds.

## Communications

- Design partner: owner sends the note. Engineering supplies the SHA and the deny reason, not customer data.
- Public status: no page is turned on by this playbook.
- Support escalation: owner names the on-call. None is assigned here.

## Evidence retention

Keep the grant id, reason code, SHA, and time. Redact prompts and secrets before they leave the evidence store.

## Gate

The playbook is ready for an operator. It is **not** a completed drill.
