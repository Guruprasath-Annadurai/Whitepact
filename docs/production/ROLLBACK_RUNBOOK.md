# Rollback Runbook

## Application rollback

1. Redeploy previous **container digest** (not tag alone).
2. Confirm `WHITEPACT_ENV` and secrets unchanged unless incident requires rotation.
3. Hit `/api/health` and governance smoke path.

## Database rollback

- Alembic migrations are often **forward-only**. Do not assume `alembic downgrade` is safe.
- Classify migration in PR: `BACKWARD_COMPATIBLE` vs `BREAKING`.
- If schema advanced with incompatible code rolled back, **stop traffic** until forward fix or tested downgrade.

## Feature flags / Formula mode

- Future `FormulaRolloutMode` changes must be rolled back independently of container (config map).
- Never roll back into a mode that bypasses authority.

## Validation

- Error rate and 5xx drop
- Revocation epoch monotonicity preserved
- No cross-tenant test failures on staging replay
