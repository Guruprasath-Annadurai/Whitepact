# WhitePact Operation Atlas — M13-X Resume Instructions

**Milestone:** M13-X  
**Worktree Directory:** `/Users/ag/.gemini/antigravity/scratch/whitepact-m13x`  
**Git Branch:** `security/whitepact-m13x-platform`  
**Base Commit:** `8cb692b97063cf2b63897d8bba07842be4b0d00a`  

---

## 1. Environment Setup

### 1.1 Python Virtual Environment
Use the dedicated project venv:
```bash
export VENV_PY=/Users/ag/Whitepact/.venv/bin/python
export VENV_PYTEST=/Users/ag/Whitepact/.venv/bin/pytest
export PYTHONPATH=src:.
```

### 1.2 PostgreSQL Database
A PostgreSQL 16 container/service must be running. Test suites resolve connection parameters via `src/responsibleai/enterprise/authority/service.py:resolve_admin_url()`:
```bash
# Default local instance:
# host=localhost port=55432 user=wp password=wp dbname=postgres
```

---

## 2. Test Execution & Verification

### 2.1 Backend Platform & Contract Tests
Run newly implemented M13-X tests and security regression suites:
```bash
PYTHONPATH=src:. $VENV_PYTEST \
  tests/test_m13x_webauthn_origin_binding.py \
  tests/test_m13x_application_inventory_contract.py \
  tests/test_m13r3_security_regression.py \
  tests/test_m12fs_root_hardening.py \
  -o addopts="" -v
```

### 2.2 Independent Immutable Security Suite
Run the full independent M13-R2 regression suite against live PostgreSQL:
```bash
PYTHONPATH=src:. $VENV_PYTEST tests/independent_m13r2/ -o addopts="" -q
```

### 2.3 Frontend Vitest Suite
Link dependencies and run frontend unit and contract tests:
```bash
cd web
npm test
```

### 2.4 License and Header Check
Verify all first-party files have valid copyright and SPDX headers:
```bash
$VENV_PY scripts/manage_license_headers.py --check
```

---

## 3. Git Operations & Commits
- Always sign commits: `git commit -s`
- Committer identity: `Techezz Infos <Techezzinfos@gmail.com>`
- Never force-push or rebase published PR branches (`#206`, `#208`, `#209`, `#210`).
