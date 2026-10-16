# WhitePact Operation TITAN — Resume Instructions

**Branch:** `antigravity/whitepact-m13-titan`  
**Worktree:** `/Users/ag/.gemini/antigravity/scratch/whitepact-m13-titan`  

---

## 1. Environment & Setup

- **Python Virtualenv:** `/Users/ag/.gemini/antigravity/scratch/whitepact/.venv`
- **PostgreSQL Database:** Requires running local PostgreSQL on standard port `5432` with user `postgres` or `wp`. Use `tests.pg_test_url.isolated_pg_url` for ephemeral databases.
- **Node.js Environment:** Node 20+ in `web/`. Run `npm test` or `npm run lint`.

---

## 2. Fast Verification Commands

```bash
# 1. Full repository Ruff checks
/Users/ag/.gemini/antigravity/scratch/whitepact/.venv/bin/ruff check src/ tests/ sdk/python/
/Users/ag/.gemini/antigravity/scratch/whitepact/.venv/bin/ruff format --check src/ tests/ sdk/python/

# 2. P0/P1 Titan Security Contracts (PostgreSQL)
PYTHONPATH=src /Users/ag/.gemini/antigravity/scratch/whitepact/.venv/bin/pytest tests/test_m13_titan_security_contracts.py -o addopts="" -v

# 3. WebAuthn origin and Application Inventory tests
PYTHONPATH=src /Users/ag/.gemini/antigravity/scratch/whitepact/.venv/bin/pytest tests/test_m13i2_atlas_origin_configuration.py tests/test_m13x_webauthn_origin_binding.py tests/test_m13x_application_inventory_contract.py -o addopts="" -v

# 4. Web client tests
cd web && npm test src/test/m13x-application-reader.test.ts && npm run lint

# 5. Integrity and trust checks
/Users/ag/.gemini/antigravity/scratch/whitepact/.venv/bin/python3 scripts/manage_license_headers.py --check
/Users/ag/.gemini/antigravity/scratch/whitepact/.venv/bin/python3 scripts/check_pinned_actions.py
/Users/ag/.gemini/antigravity/scratch/whitepact/.venv/bin/python3 scripts/check_trust_regressions.py
```

---

## 3. Next Engineering Phase (Post M13-I2 Clearance)

Once Codex reviews and merges the security foundation:
1. Proceed with end-to-end customer journey testing (`scripts/engineering/m13i2_customer_journey.py`).
2. Implement browser automation and step-up ceremony verification via Playwright/CDP (`scripts/engineering/m13i3_browser_journey.py`, `tests/js/m13i3-real-webauthn.mjs`).
3. Formal release readiness audit for M13 milestone sign-off.
