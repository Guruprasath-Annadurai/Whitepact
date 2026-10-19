# IRONCLAD migration compatibility

Final qualification update (2026-10-19): frozen implementation HEAD `ccf4e8cc80f1de52a0a9b445298055ac581f53e1`, tree `c7bef348b9dcea2e55a86d4b01f357fb1498ecd2`, parent `47fc55a1591890f18c06333b4f187d091535719d`. Draft PR #221 targets `codex/whitepact-m13-absolute-convergence`. Evidence-only branch adds tests/reports; implementation equivalence is checked independently. The current results below supersede historical pending statements retained later in this audit trail. M13 OPEN. GLOBAL PRODUCTION NO-GO.

## Current exact-source evidence

Exact-source fresh local PostgreSQL: **6 PASS in101.13s**, comprising four unchanged downgrade guards, runtime schema compatibility and disposable-role retirement. Receipt `/private/tmp/m13-ironclad-ccf4-postgres.xml`. PostgreSQL16 Linux customer journeys independently initialize fresh0065 databases on both Python versions (run39243120761). Full matrix still reports all24 historical head-assertion failures; they remain unchanged FAIL gates. Mandatory0065→0064 downgrade is refused atomically. Retention metadata is insufficient; old pooled roles/binaries require verified retirement before operational cutover. No live role cutover or old deployed-binary qualification is claimed.

## Safety verdict

Retention metadata alone does not protect a0064 application that ignores mandatory step-up flags. Preserve0065 downgrade refusal: PostgreSQL ACCESS EXCLUSIVE lock plus mandatory-row check must raise before dropping protections or revision change. Immutable original test blob f4d5731e9b2792b18a69e1fcfd475164ee4f0898 remains unchanged. This checkpoint changes no migration.

Original `7939341f` independently ran4 real PostgreSQL downgrade guard cases per Python version: atomic mandatory refusal, nonmandatory row roundtrip, failedDDL rollback, concurrent mandatory writer. This is historical evidence, not new-head execution. Current binary revision marker fencing and disposable-role NOLOGIN/connection termination tests are distinct from real historical binary compatibility and operational cutover. No live role retirement is authorized or performed. Historical pooled connections remain an operational risk until retired with independent receipts.

## Original 24 failures individually dispositioned

Each listed case stops on expected historical head0063 versus actual0065, except immutable0063→0064 roundtrip expecting0064 versus0065. Therefore each later invariant in that test remains unexecuted at that assertion. Original tests remain failing and unchanged; current-head counterparts must preserve their schema/data invariants.

| File | Exact function/case |
|---|---|
| independent_m13r2/test_m13r_migration_roundtrip.py | test_0063_upgrade_0064_constraints_and_safe_empty_downgrade |
| test_auth_real_postgres.py | test_one_canonical_alembic_head |
| test_historical_postgres_migrations.py | test_downgrade_and_reupgrade_idempotence |
| same | test_fresh_install_to_head_postgres |
| same | test_one_canonical_alembic_head |
| same | test_upgrade_0042_to_head_preserves_data_and_invariants |
| same | test_upgrade_0043_to_head_preserves_trust_fabric_and_invariants |
| same | test_upgrade_0044_to_head_preserves_iam_and_invariants |
| test_migration_ownership_canonical.py | test_alembic_single_head_is_0063_api_key_mfa_timestep |
| test_phase1_migrations.py | test_one_canonical_head |
| same | test_postgres_upgrade_paths[0029] |
| same | test_postgres_upgrade_paths[0032] |
| same | test_postgres_upgrade_paths[base] |
| same | test_supported_upgrade_paths[0029] |
| same | test_supported_upgrade_paths[0032] |
| same | test_supported_upgrade_paths[base] |
| test_phase4_migrations.py | test_one_canonical_alembic_head |
| test_phase5_migrations.py | test_fresh_schema_to_0045_postgres |
| same | test_one_canonical_alembic_head |
| test_phase7a_migrations.py | test_single_head_0053 (assertion currently0063) |
| same | test_upgrade_downgrade_0050_0053_when_empty |
| test_postgres_migrations.py | test_one_canonical_alembic_head |
| test_v1_customer_journey.py | test_fresh_postgres_health_ready_and_nonprod_preflight |
| same | test_historical_0057_upgrade_then_signup |

No passing downgrade/re-upgrade alone qualifies old-binary operation. Fresh exact-head regression and actual historical-binary tests remain required. Maintainer decision is required to replace historical head assertions; no protected history or tests rewritten.
