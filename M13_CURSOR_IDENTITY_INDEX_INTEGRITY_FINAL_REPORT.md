# M13 identity index integrity

Repair SHA: `202db0b24ac5ea15c1d6009df3e0771741b964d8` on `cursor/m13-identity-trust-boundary-099e`. PR https://github.com/Guruprasath-Annadurai/Whitepact/pull/235.

## Original failure

Codex PR #236, commit `abdcef3d441b58968b9ac5eb05ed0b07b0bb2eea`, hosted run https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/40556236572.

`ensure_identity_session_uniqueness()` returned as soon as `pg_indexes` contained `uq_identity_verification_provider_session`. Three disposable PostgreSQL indexes with that name bypassed the guarantee:

1. A non-unique index on `(provider, provider_reference_id)`.
2. A unique index on `(user_id, provider_reference_id)`.
3. A unique index on `(provider, provider_reference_id) WHERE status='VERIFIED'`.

Codex's `test_named_but_ineffective_session_index_cannot_qualify_startup` then inserted two `REVIEW_REQUIRED` rows with the same provider session. Startup accepted them. Those assertions were copied unchanged into `tests/test_codex_m13_schema_index_contract.py`. Codex PR #236 and Argon PR #234 were not modified.

## Catalog rule

On PostgreSQL, and only when `alembic_version` is exactly `0067`, the public index is accepted only when all of the following hold:

- relation `identity_verifications`
- `indisunique`, not a primary key, not an exclusion constraint
- `indimmediate` (not a deferred uniqueness check)
- `indisvalid`, `indisready`, and `indislive`
- `indpred` and `indexprs` are null (no partial predicate, no expression)
- key length 2 and key columns exactly `provider`, `provider_reference_id`

If the name is missing, the previous create path remains: duplicate sessions raise `IdentitySessionConflictError` and are not deleted; otherwise `CREATE UNIQUE INDEX` runs and the new catalog row is checked in the same transaction. A failed check rolls that build back.

If the name exists but the catalog row fails the rule, startup raises `IdentitySessionIndexInvalidError`. The index is not dropped and identity rows are not deleted. `SUPPORTED_POSTGRES_REVISIONS` stays `{0067}`. Revision `0068` is not revived. The five-line `UniqueConstraint` in `src/responsibleai/db/engine.py` is unchanged.

## Proof

PostgreSQL 16.15. `WHITEPACT_TEST_PG_ADMIN_URL=postgresql://wp:wp@127.0.0.1:5432/postgres`.

CPython 3.12.3 and 3.11.11 each ran 23 tests, all passed:

- `tests/test_codex_m13_schema_index_contract.py` (the three malformed indexes, plus missing-index rebuild and atomic duplicate insert)
- `tests/test_m13_identity_session_schema.py` (valid index, repeated startup, duplicate sessions left in place, incompatible named index left in place, startup refusal)
- `tests/test_m13_runtime_schema_compatibility.py` (non-`0067` stamps, including `0068`, still refuse)
- `tests/test_m13_identity_trust_boundary.py` (issuance gate and concurrent PostgreSQL callback)

`ruff check` on the changed Python files passed.

## Hosted qualification queued

These runs were queued at 28 Oct 2026, 12:21 AM IST for `a463e8b7`, which contains repair `202db0b24ac5ea15c1d6009df3e0771741b964d8`:

- I1 https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/40563834113
- Product https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/40563834097
- Sovereign https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/40563834175
- Absolute Runtime https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/40563834092

They were still running when this note was written. Absolute Runtime's unit job is still expected to fail on the untouched Codex recovery gate (`Verified offline operator recovery session required`). I1's historical DCO denial and the blocked customer journey (exit 2) are also unchanged.

## Independent retest

Please re-run `tests/test_codex_m13_schema_index_contract.py` on Python 3.11 and 3.12 against PostgreSQL 16, on the repair SHA below, without changing the assertions. A same-named non-unique, wrong-column, or partial index must still leave both conflicting rows stored and must still refuse startup.

The canonical customer journey stays blocked until a real approved provider exists.

M13 remains open. Production remains no-go.
