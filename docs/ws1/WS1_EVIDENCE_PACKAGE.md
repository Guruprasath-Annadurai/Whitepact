# WS-1 evidence package — CLI, packaging & product identity

| Field | Value |
|-------|--------|
| Workstream | Phase 1 WS-1 only |
| Base SHA | `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` |
| Implementation branch | `cursor/whitepact-ws1-cli-identity-f7a9` |
| Implementation HEAD (installation hardening) | _pending push — see PR #129_ |
| Prior qualified HEAD | `1dcb622d4963e6e08bfba562a387a3cfb15620c0` |
| Prior qualified CI run | [36704297202](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36704297202) — **success** |

## Finding scope (do not conflate)

| ID | WS-1 addresses | Status after WS-1 |
|----|----------------|-------------------|
| **BLK-P0-01** | CLI launches BiasBuster instead of WhitePact | **Mitigated in tree** — `whitepact` → `whitepact.cli:main`; Antigravity installation retest required |
| **BLK-P0-05** | Published package/product naming mismatch | **Open** — PyPI distribution remains `rai-governance-platform`; WS-1 documents identity only, **no** distribution rename or PyPI publish |

## Changed files (inventory)

| Path | Change |
|------|--------|
| `src/whitepact/cli.py` | Product CLI; **lazy sovereign/dashboard command registration** |
| `src/biasbuster/cli.py` | Sovereign commands removed; BiasBuster-only top-level |
| `pyproject.toml` | `whitepact` → `whitepact.cli:main` |
| `scripts/wheel_default_install_smoke.sh` | **CREATE** — default wheel install smoke |
| `scripts/wheel_dashboard_install_smoke.sh` | **CREATE** — `[dashboard]` wheel smoke |
| `.github/workflows/ci.yml` | **CREATE** `wheel-smoke` job (Py3.11 + Py3.12) |
| `tests/test_whitepact_cli_entrypoint.py` | Entrypoint regression + lazy-import guard |
| `tests/test_mcp_server.py` | `TestCliEntryPoints` — distinct WS-1 script mappings |
| `tests/sovereign/test_cli_sovereign.py` | Import `whitepact.cli` |
| `docs/PACKAGE_IDENTITY.md` | CLI entry-point table |
| `MIGRATION_WHITEPACT_V2.md` | Section 4 target entry |
| `docs/phase0/*` | SHA reconciliation + conditional acceptance |

## Acceptance evidence

### 1. Default wheel install (no extras)

Built wheel from sdist (`python -m build`), clean venv, `pip install dist/*.whl` only:

```bash
env -u PYTHONPATH bash scripts/wheel_default_install_smoke.sh
```

Verifies:

- `whitepact --help` — **WhitePact** product CLI (no import-time sovereign stack)
- `whitepact --version` / `whitepact info`
- `biasbuster --help` — legacy entry unchanged
- `whitepact doctor` — **ClickException** with `pip install 'rai-governance-platform[dashboard]'` guidance (no traceback)

### 2. Wheel install with `[dashboard]`

```bash
env -u PYTHONPATH bash scripts/wheel_dashboard_install_smoke.sh
```

Verifies `whitepact doctor --json` returns `"checks"` (sovereign path loads when extras present).

### 3. CLI behavior (editable / dev install)

- `whitepact doctor --json` — sovereign diagnostic (exit 0) when dashboard stack available
- `whitepact bias run --help` — bias probe help (nested under `bias`)
- `biasbuster run --help` — unchanged legacy entry

### 4. Product identity docs

- `docs/PACKAGE_IDENTITY.md`
- `MIGRATION_WHITEPACT_V2.md` §4

### 5. Backward compatibility

- `biasbuster` / `responsibleai` console scripts still `biasbuster.cli:main`
- `tests/test_cli.py` — biasbuster commands unchanged

### 6. Regression tests

```bash
pytest tests/test_whitepact_cli_entrypoint.py tests/sovereign/test_cli_sovereign.py tests/test_cli.py \
  tests/test_mcp_server.py::TestCliEntryPoints -q --no-cov
```

### 7. CI (exact HEAD)

| Field | Value |
|-------|--------|
| HEAD SHA | _updated after green `wheel-smoke` + full workflow on installation-hardening commit_ |
| Run URL | _pending_ |
| `Wheel install smoke` (Py3.11 / Py3.12) | _pending_ |
| `Lint · Type-check · Test` (Py3.11 / Py3.12) | _pending_ |
| Workflow conclusion | _pending_ |

Prior qualified run: [36704297202](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36704297202) on `1dcb622` (pre-installation-hardening).

### 8. Antigravity

Independent retest of **default-install** CLI launch (post lazy-import fix) on WS-1 HEAD.

## Distribution

- **No PyPI publish** in WS-1.
- PyPI distribution name remains `rai-governance-platform` (no rename migration).
