# Legacy governance static surface (M2 / BLK-P0-06)

## Production / unified SaaS

- **Mounted:** `src/responsibleai/dashboard/static/` only (allowlisted paths).
- **Not mounted:** `src/responsibleai/dashboard/legacy_templates/` (retired shell HTML, `app.js`, `i18n.js`, `app.css`).
- **Enforcement:** `UnifiedSaaSLegacyRetirementMiddleware` + `UnifiedSaasStaticFiles` allowlist.

## Community development

Legacy shell assets are mapped to URL paths under `/static/` via `legacy_shell_disk_path()` without placing files under the public static tree.

## Regression

- `tests/test_ws3_unified_saas_legacy_frontend.py` — BYPASS-01/02 matrices
- `tests/test_ws3_static_surface_inventory.py` — static tree classification
- `src/responsibleai/dashboard/static_surface_inventory.py` — deterministic inventory

## Frozen CI candidate (do not move without Antigravity disposition)

See `/opt/cursor/artifacts/m2_frozen_ci_candidate_893d34a.json`.
