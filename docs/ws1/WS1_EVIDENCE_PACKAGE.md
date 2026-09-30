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
| Documentation-only | `e2553ff…` / `1b4cb04…` | `e2553ff`, `1b4cb04` | CI cross-references; **no code change** |

**Milestone M0:** Engineering closure complete on qualified tree `b5641b7` (code `5cfa1f0`). Pending Antigravity focused confirmation of closure conditions; **founder merge of PR #129** is a separate approval gate.

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

## Post-qualification dependency security update

Previously qualified WS-1 closure code tree **`b5641b740df63a8a408a900186f1d3cd00803174`** is unchanged in history; PR #129 later picked up documentation-only tips (`fd11815`) that exposed a **new M0 dependency security gate** when advisory data caught up with pinned tooling.

### Advisory (reproduced locally, CI-identical install)

Install mode (matches `.github/workflows/ci.yml`):

```bash
pip install -e ".[dev,openai,anthropic,sso,sentiment,postgres]"
pip install --require-hashes -r requirements-security.lock
pip-audit --skip-editable \
  --ignore-vuln PYSEC-2026-597 \
  --ignore-vuln PYSEC-2026-3740
```

| Field | Value |
|-------|--------|
| **Package** | `urllib3` |
| **Installed (vulnerable) version** | `2.7.0` (from `requirements-security.lock`, not from default `pyproject` pins) |
| **Identifiers** | **CVE-2026-97687** (GHSA-8988-9cw3-xx77), **CVE-2026-97688** (GHSA-gh4c-6fx4-qh6g), **CVE-2026-97689** (GHSA-vxq7-64xx-v4gw) |
| **Severity** | High — proxy TLS mis-binding / certificate verification confusion (97687); High — CPU DoS via Deflate streaming decoder loop (97688); Medium — memory pressure via oversized chunked chunk-size fields when streaming (97689) |
| **Fixed version** | **`2.8.0`** |
| **Direct vs transitive** | **Transitive** — lock comment `# via requests` (pulled by `pip-audit` → `requests` / `cachecontrol` in `requirements-security.in` compile tree) |
| **Top-level introducer** | `pip-audit` / `bandit` security tooling lock (`requirements-security.in`), not a `pyproject.toml` direct dependency |
| **Install profiles** | Present after CI installs **dev + optional extras matrix** and then applies **`requirements-security.lock`** (hashed tooling install **downgraded** resolver-chosen `urllib3` 2.8.0 → 2.7.0). Default wheel-only install resolves `urllib3` via HTTP client stacks when optional integrations are present; **`[dashboard]`** and CI extras increase `requests`/HTTP usage. |

### Exposure (separate from remediation)

`urllib3` sits on the HTTP transport path for **`requests`**-based clients (e.g. LangChain/LangSmith, Google ADK/GenAI, OpenTelemetry OTLP HTTP exporter, and CI `pip-audit` itself). WhitePact core default dependencies use **`httpx`**, but CI and common optional extras still load **`urllib3`** at runtime. The advisories affect HTTPS proxy TLS configuration, streamed compressed responses, and streamed chunked bodies from **untrusted HTTP servers** — not a single WhitePact API call site, but the library is **reachable** whenever those HTTP stacks handle external responses. Remediation does not depend on proving a specific in-repo call pattern.

### Remediation

| Item | Before | After |
|------|--------|-------|
| `requirements-security.lock` | `urllib3==2.7.0` | `urllib3==2.8.0` (regenerated via `uv pip compile` per `requirements-security.in`) |
| `uv.lock` | `urllib3` 2.7.0 | `urllib3` 2.8.0 (`uv lock --upgrade-package urllib3`) |

No `pip-audit --ignore-vuln` entries were added for these CVEs. No application behavior or package identity changes.

### Requalified merge candidate

| Field | Value |
|-------|--------|
| **Dependency remediation SHA** | `a7552bd6c7f38bbbc696f14d5eb7fa820e53cb10` (DCO-signed; `urllib3` lock bump only) |
| **Merge-candidate SHA (incl. evidence + CI stability)** | `8d988283e658a00aadfd7e89c66290801acd09c5` |
| **Final CI (full workflow success)** | https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36782345920 — **success** on `8d98828` |

Local requalification on dependency commit: default + `[dashboard]` wheel smokes **PASS**; WS-1 CLI regression bundle **24 passed**; `pip-audit` (CI flags) **clean**; Self-Conducted Security Scan path (`pip install -e .` + lock) **clean**.
