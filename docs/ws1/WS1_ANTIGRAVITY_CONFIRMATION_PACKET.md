# WS-1 — Antigravity final confirmation packet (M0)

**Purpose:** Focused independent confirmation after engineering closure.  
**Do not** conflate documentation-only branch tips with CI-qualified code trees.

## Qualified artifacts (frozen)

| Artifact | SHA / URL |
|----------|-----------|
| Implementation (installation retest) | `0207ed83ad1e0560ef270ae8c24ccde294d8fa2c` |
| Closure code tree | `b5641b740df63a8a408a900186f1d3cd00803174` (identical to `5cfa1f0`) |
| Implementation CI | https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36712288188 — **success** |
| Exact-final-HEAD CI | https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36725514596 — **success** |
| PR | https://github.com/Guruprasath-Annadurai/Whitepact/pull/129 |

## Reproduction (default wheel, no `[dashboard]`)

```bash
git checkout b5641b740df63a8a408a900186f1d3cd00803174
env -u PYTHONPATH bash scripts/wheel_default_install_smoke.sh
env -u PYTHONPATH bash scripts/wheel_dashboard_install_smoke.sh
```

## Expected results

- `whitepact --help`, `--version`, `info` succeed on default install.
- `whitepact doctor --json` exits **1** with dashboard install guidance; **no traceback**.
- With `[dashboard]`, `whitepact doctor --json` includes `"checks"`.
- `biasbuster --help` unchanged.
- **BLK-P0-01:** VERIFIED_CLOSED in qualified tree.
- **BLK-P0-05:** remains **OPEN** (PyPI name `rai-governance-platform`; no publish/rename in WS-1).

## Prior Antigravity disposition

Installation retest: **CONDITIONAL PASS** — engineering closure conditions met in `5cfa1f0` / CI `b5641b7`.

## Founder merge gate

Merge of PR #129 requires founder approval; not executed by engineering automation.

---

## Post-qualification dependency security — Antigravity reconfirmation (M0)

**Status:** **REQUESTED** (after green required CI on the requalified merge-candidate SHA documented in `docs/ws1/WS1_EVIDENCE_PACKAGE.md` § Post-qualification dependency security update).

Please confirm:

1. Original WS-1 closure conditions on qualified tree **`b5641b7`** remain satisfied; the only intentional code delta for this gate is **`urllib3` 2.8.0** lock remediation (`requirements-security.lock`, `uv.lock`).
2. Dependency remediation does **not** regress CLI / product identity behavior (`whitepact` entrypoint, lazy sovereign imports, wheel smokes).
3. **Vulnerability scans pass** — CI `pip-audit` (Python 3.11/3.12) and Self-Conducted Security Scan `pip-audit` on the merge candidate.
4. **No unrelated application changes** entered the candidate beyond lock regeneration (and any CI-stability test harness adjustment if required for a green rollup).
5. **BLK-P0-01** remains **VERIFIED_CLOSED**.
6. **BLK-P0-05** remains **OPEN** (no PyPI rename/publish in WS-1).

Do **not** treat founder merge as approved until this focused confirmation is recorded.
