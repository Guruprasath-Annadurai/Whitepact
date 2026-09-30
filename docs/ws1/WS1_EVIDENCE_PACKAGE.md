# WS-1 evidence package — CLI, packaging & product identity (final closure)

| Field | Value |
|-------|--------|
| Workstream | Phase 1 WS-1 only |
| Base SHA | `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` |
| Implementation branch | `cursor/whitepact-ws1-cli-identity-f7a9` |
| PR | [#129](https://github.com/Guruprasath-Annadurai/Whitepact/pull/129) (not merged) |

## Commit lineage (do not conflate)

| Role | Full SHA | Short | Notes |
|------|----------|-------|--------|
| **CI-qualified WS-1 implementation** | `0207ed83ad1e0560ef270ae8c24ccde294d8fa2c` | `0207ed8` | Lazy sovereign CLI, wheel-smoke CI job, SPDX on smoke scripts. **Antigravity installation retest target.** |
| Implementation CI | [36712288188](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36712288188) | | **success** on `0207ed8` |
| Documentation-only (interim) | `f4a1ef7…` | `f4a1ef7` | Recorded `0207ed8` + run 36712288188; no code change |
| **Closure implementation** | `5cfa1f049bd974c40804db462d863d23f86af544` | `5cfa1f0` | Hardened `wheel_default_install_smoke.sh` + evidence revision |
| **Final HEAD (exact-final-HEAD CI)** | `b5641b740df63a8a408a900186f1d3cd00803174` | `b5641b7` | Empty CI retrigger; **identical code tree to `5cfa1f0`** |
| Final closure CI | [36725514596](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36725514596) | | **success** on `b5641b7` |
| Documentation-only (branch tip) | `e2553ff…` | `e2553ff` | Records final CI in this package; **no code change** |

Prior WS-1 entrypoint qualification: `1dcb622` — [36704297202](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36704297202).

## Finding scope

| ID | WS-1 scope | Disposition |
|----|------------|-------------|
| **BLK-P0-01** | `whitepact` must be product CLI; default install must launch | **VERIFIED_CLOSED** in the CI-qualified implementation tree (`0207ed8`) — Antigravity final installation retest **CONDITIONAL PASS** (see § Antigravity) |
| **BLK-P0-05** | PyPI / distribution naming vs product identity | **OPEN** — distribution remains `rai-governance-platform`; **no** rename migration or PyPI publication in WS-1 |

## Changed files (inventory — WS-1 implementation + closure)

| Path | Change |
|------|--------|
| `src/whitepact/cli.py` | WhitePact product CLI; lazy sovereign/dashboard registration (`0207ed8`) |
| `src/biasbuster/cli.py` | BiasBuster-only top-level CLI |
| `pyproject.toml` | `whitepact` → `whitepact.cli:main` |
| `scripts/wheel_default_install_smoke.sh` | Default wheel smoke; strict `doctor` exit/guidance/traceback checks (closure) |
| `scripts/wheel_dashboard_install_smoke.sh` | `[dashboard]` wheel smoke |
| `.github/workflows/ci.yml` | `wheel-smoke` job (Python 3.11 + 3.12) |
| `tests/test_whitepact_cli_entrypoint.py` | Entrypoint + lazy-import regression |
| `tests/test_mcp_server.py` | `TestCliEntryPoints` |
| `tests/sovereign/test_cli_sovereign.py` | Sovereign commands via `whitepact.cli` |
| `docs/PACKAGE_IDENTITY.md` | Product / entry-point table |
| `MIGRATION_WHITEPACT_V2.md` | §4 CLI migration |
| `docs/ws1/WS1_EVIDENCE_PACKAGE.md` | This package |
| `docs/phase0/*` | Phase 0 registers (conditional acceptance) |

## Acceptance evidence

### 1. Default wheel install (no extras)

```bash
env -u PYTHONPATH bash scripts/wheel_default_install_smoke.sh
```

Asserts:

- `whitepact --help`, `--version`, `info`; `biasbuster --help`
- `whitepact doctor --json` exits **1** (not 0), prints exact guidance  
  `This command requires optional dashboard dependencies. Install with: pip install 'rai-governance-platform[dashboard]'`
- No `Traceback (most recent call last)` in doctor output

### 2. Wheel install with `[dashboard]`

```bash
env -u PYTHONPATH bash scripts/wheel_dashboard_install_smoke.sh
```

Asserts `whitepact doctor --json` contains `"checks"` (exit 0).

### 3. CI — implementation qualification (`0207ed8`)

Run: https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36712288188  
Workflow conclusion: **success**

| Job | Python | Result |
|-----|--------|--------|
| Wheel install smoke | 3.11 | **success** |
| Wheel install smoke | 3.12 | **success** |
| Lint · Type-check · Test | 3.11 | **success** |
| Lint · Type-check · Test | 3.12 | **success** |
| Build distribution | 3.12 | **success** |
| Helm chart lint | — | **success** |
| i18n unit tests | — | **success** |
| Frontend closure | — | **success** |
| Accessibility (WCAG2AA) | — | **success** |

### 4. CI — final closure HEAD (`b5641b7`, same tree as `5cfa1f0`)

Run: https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36725514596  
Workflow conclusion: **success**

| Job | Python | Result |
|-----|--------|--------|
| Wheel install smoke | 3.11 | **success** |
| Wheel install smoke | 3.12 | **success** |
| Lint · Type-check · Test | 3.11 | **success** |
| Lint · Type-check · Test | 3.12 | **success** |
| Build distribution | 3.12 | **success** |
| Helm chart lint | — | **success** |
| i18n unit tests | — | **success** |
| Frontend closure | — | **success** |
| Accessibility (WCAG2AA) | — | **success** |

### 5. Regression tests (local / CI subset)

```bash
pytest tests/test_whitepact_cli_entrypoint.py tests/sovereign/test_cli_sovereign.py \
  tests/test_mcp_server.py::TestCliEntryPoints -q --no-cov
```

### 6. Antigravity

| Item | Value |
|------|--------|
| Retest target commit | `0207ed83ad1e0560ef270ae8c24ccde294d8fa2c` |
| Outcome | **CONDITIONAL PASS** — implementation accepted |
| Conditions for full sign-off | (1) Finalize this evidence package with verified SHAs and CI matrix; (2) Harden default-install smoke so `doctor` exit status and guidance are asserted without masking failures. **Met** in `5cfa1f0` / CI `b5641b7` ([36725514596](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36725514596)). **No** WS-2, merge, or PyPI publish in WS-1 |

### 7. Distribution

- **No PyPI publish** in WS-1.
- PyPI name remains `rai-governance-platform`.
