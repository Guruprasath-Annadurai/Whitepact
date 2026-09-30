# WS-1 evidence package — CLI, packaging & product identity

| Field | Value |
|-------|--------|
| Workstream | Phase 1 WS-1 only |
| Base SHA | `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` |
| Implementation branch | `cursor/whitepact-ws1-cli-identity-f7a9` |
| Implementation HEAD (qualified) | `1dcb622d4963e6e08bfba562a387a3cfb15620c0` |
| WS-1 code commit (same tree) | `787ab98ac7ebe85bf1d769be1e2ce3d0a52fdcdb` |
| Qualified CI run | [36704297202](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36704297202) — **success** |

## Finding scope (do not conflate)

| ID | WS-1 addresses | Status after WS-1 |
|----|----------------|-------------------|
| **BLK-P0-01** | CLI launches BiasBuster instead of WhitePact | **Mitigated in tree** — `whitepact` → `whitepact.cli:main`; Antigravity retest required |
| **BLK-P0-05** | Published package/product naming mismatch | **Open** — PyPI distribution remains `rai-governance-platform`; WS-1 documents identity only, **no** distribution rename or PyPI publish |

## Changed files (inventory)

| Path | Change |
|------|--------|
| `src/whitepact/cli.py` | **CREATE** — WhitePact product CLI |
| `src/biasbuster/cli.py` | Sovereign commands removed; BiasBuster-only top-level |
| `pyproject.toml` | `whitepact` → `whitepact.cli:main` |
| `tests/test_whitepact_cli_entrypoint.py` | **CREATE** — entrypoint regression |
| `tests/test_mcp_server.py` | `TestCliEntryPoints` — distinct WS-1 script mappings |
| `tests/sovereign/test_cli_sovereign.py` | Import `whitepact.cli` |
| `docs/PACKAGE_IDENTITY.md` | CLI entry-point table |
| `MIGRATION_WHITEPACT_V2.md` | Section 4 target entry |
| `docs/phase0/*` | SHA reconciliation + conditional acceptance |

## Acceptance evidence

### 1–2. Clean install & `whitepact --help`

```bash
python3 -m venv /tmp/wp-ws1-venv
/tmp/wp-ws1-venv/bin/pip install "/path/to/Whitepact[dashboard]"
/tmp/wp-ws1-venv/bin/whitepact --help
/tmp/wp-ws1-venv/bin/whitepact info
```

Expected: help text describes **WhitePact — AI governance platform CLI**; `info` shows `rai-governance-platform`.

### 3. CLI behavior

- `whitepact doctor --json` — sovereign diagnostic (exit 0)
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
| HEAD SHA | `1dcb622d4963e6e08bfba562a387a3cfb15620c0` |
| Run URL | https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36704297202 |
| Py3.11 `Lint · Type-check · Test` | **success** |
| Py3.12 `Lint · Type-check · Test` | **success** |
| Workflow conclusion | **success** |

Prior run [36694625330](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36694625330) failed on `TestCliEntryPoints` (fixed in `787ab98`). Run [36699437306](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36699437306) had Py3.11 **success** but workflow **cancelled** at 45m before Py3.12 finished.

### 8. Antigravity

Independent retest of BLK-P0-01 on WS-1 HEAD.

## Distribution

- **No PyPI publish** in WS-1.
- PyPI distribution name remains `rai-governance-platform` (no rename migration).
