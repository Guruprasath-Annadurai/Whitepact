# WhitePact Operation TITAN — Test Evidence & Proof Matrix

**Execution Date:** 2026-10-16  
**Platform:** macOS Darwin (arm64) / Python 3.12.14 / PostgreSQL 16  
**Branch:** `antigravity/whitepact-m13-titan`  

---

## 1. PostgreSQL Security Contract Acceptance Suite (`tests/test_m13_titan_security_contracts.py`)

Command:
```bash
PYTHONPATH=src pytest tests/test_m13_titan_security_contracts.py -o addopts="" -v
```

Output:
```
============================= test session starts ==============================
platform darwin -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/ag/.gemini/antigravity/scratch/whitepact-m13-titan
configfile: pyproject.toml
plugins: langsmith-0.12.1, cov-7.1.0, asyncio-1.4.0, hypothesis-6.167.1, anyio-4.15.1, respx-0.23.1
asyncio: mode=Mode.AUTO, debug=False

tests/test_m13_titan_security_contracts.py::test_postgres_disable_application_transactional_rollback PASSED [ 20%]
tests/test_m13_titan_security_contracts.py::test_postgres_disable_application_atomic_cascade_and_cross_worker_grant_invalidation PASSED [ 40%]
tests/test_m13_titan_security_contracts.py::test_postgres_concurrent_register_agent_vs_disable_application_serialization PASSED [ 60%]
tests/test_m13_titan_security_contracts.py::test_capability_projection_evaluates_root_expiry_consent_app_state_and_policies PASSED [ 80%]
tests/test_m13_titan_security_contracts.py::test_organization_rename_workspace_and_concurrency_preconditions PASSED [100%]

======================== 5 passed in 132.26s (0:02:12) =========================
```

**Proof Outcomes:**
1. Transactional rollback proves mid-transaction database or worker interruption rolls back 100% of application, agent, delegation, and epoch mutations on PostgreSQL.
2. Multi-hop cascade revokes intermediate and leaf delegations, revokes consent proofs, advances the epoch, and causes Worker B to reject pre-issued `ExecutionAuthorization` permits with `StaleRevocationEpochError`.
3. 6 concurrent registration workers racing against `disable_application` leave exactly 0 active agents under the disabled application.
4. Capability projection strictly marks expired root authority or expired consent as `EXPIRED`, and policy-denied actions as `POLICY_DENIED`.
5. Organization renames with workspace cookie mismatch or stale expected name return `409 Conflict`.

---

## 2. WebAuthn Origin Enforcement Suites

Commands:
```bash
PYTHONPATH=src pytest tests/test_m13i2_atlas_origin_configuration.py tests/test_m13x_webauthn_origin_binding.py tests/test_m13x_application_inventory_contract.py -o addopts="" -v
```

Output:
```
tests/test_m13i2_atlas_origin_configuration.py::test_production_accepts_explicit_https_origin PASSED [ 10%]
tests/test_m13i2_atlas_origin_configuration.py::test_production_rejects_explicit_plain_http_origin PASSED [ 20%]
tests/test_m13i2_atlas_origin_configuration.py::test_production_rejects_missing_origin PASSED [ 30%]
tests/test_m13x_webauthn_origin_binding.py::test_dynamic_origin_binding_in_development PASSED [ 40%]
tests/test_m13x_webauthn_origin_binding.py::test_configured_origin_takes_precedence PASSED [ 50%]
tests/test_m13x_webauthn_origin_binding.py::test_non_production_rejects_untrusted_external_origin_header PASSED [ 60%]
tests/test_m13x_webauthn_origin_binding.py::test_production_ignores_forwarded_and_hostile_headers_and_enforces_rp_id PASSED [ 70%]
tests/test_m13x_application_inventory_contract.py::test_application_lifecycle_and_tenant_boundary PASSED [ 80%]
tests/test_m13x_application_inventory_contract.py::test_application_agent_association_and_cascading_disable PASSED [ 90%]
tests/test_m13x_application_inventory_contract.py::test_server_authoritative_capabilities PASSED [100%]

============================= 10 passed in 22.75s ==============================
```

---

## 3. Web Client Unit & Reader Suite

Commands:
```bash
cd web && npm test src/test/m13x-application-reader.test.ts && npm run lint
```

Output:
```
 ✓ src/test/m13x-application-reader.test.ts (12 tests) 165ms

 Test Files  1 passed (1)
      Tests  12 passed (12)
   Duration  4.11s

> whitepact-web@1.3.1 lint
> eslint .
(Clean exit, 0 lint errors)
```

---

## 4. Lint, Formatting, and Code Quality Gates

Commands:
```bash
ruff format --check src/ tests/ sdk/python/
ruff check src/ tests/ sdk/python/
```

Output:
```
955 files already formatted
All checks passed!
```

---

## 5. Security & Trust Preflight Gates

Commands:
```bash
python scripts/manage_license_headers.py --check
python scripts/check_pinned_actions.py
python scripts/check_trust_regressions.py
```

Output:
```
All tracked first-party source files contain WhitePact copyright/SPDX headers.
All GitHub Actions dependencies are pinned to immutable commit SHAs.
Non-SLSA trust regression checks passed.
```
