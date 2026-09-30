# WS-1 evidence package — CLI, packaging & product identity

| Field | Value |
|-------|--------|
| Workstream | Phase 1 WS-1 only |
| Base SHA | `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` |
| Implementation branch | `cursor/whitepact-ws1-cli-identity-f7a9` |
| Implementation HEAD | `265ad1a633da5114a5be0e209eb6b58c8214416b` |
| Closes (target) | BLK-P0-01, BLK-P0-05 (partial P3-03 docs) |

## Changed files (inventory)

| Path | Change |
|------|--------|
| `src/whitepact/cli.py` | **CREATE** — WhitePact product CLI |
| `src/biasbuster/cli.py` | Sovereign commands removed; BiasBuster-only top-level |
| `pyproject.toml` | `whitepact` → `whitepact.cli:main` |
| `tests/test_whitepact_cli_entrypoint.py` | **CREATE** — entrypoint regression |
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
pytest tests/test_whitepact_cli_entrypoint.py tests/sovereign/test_cli_sovereign.py tests/test_cli.py -q --no-cov
```

### 7. CI

Record GitHub Actions run URL on branch HEAD after push.

### 8. Antigravity

Independent retest of BLK-P0-01 on WS-1 HEAD.

## Distribution

- **No PyPI publish** in WS-1.
- PyPI distribution name remains `rai-governance-platform` (no rename migration).
