# M13-P4 test and CI matrix

**GLOBAL PRODUCTION NO-GO.** Local results below are distinct from exact-head GitHub CI. Runtime: Python 3.11.15, Node 26.0.0; local Go 1.27.2; Chromium 151.0.7922.34. CI uses Node 22 and Python 3.11/3.12. Existing dependency directories were reused read-only through ignored symlinks; temporary SDK build/install environments and the verified Go archive live under `/private/tmp`.

## Integrated local evidence

Commands run from `/private/tmp/whitepact-m13-p4` unless noted. Python executable is `/Users/ag/Whitepact/.venv/bin/python`.

| Area / exact command | Fresh result |
| --- | --- |
| `npm --prefix web test -- --maxWorkers=2` | 29 files, 264 tests PASS in 48.64s |
| `npm --prefix web run lint` | PASS |
| `npm --prefix web run build` | TypeScript and Vite PASS |
| Rebuild followed by `git diff --exit-code -- src/responsibleai/dashboard/static/whitepact` | PASS; generated assets reproduce |
| `PYTHONPATH=src python -m pytest tests/test_mcp_wave1_compatibility.py tests/test_m13p4_mcp_lifecycle.py -o addopts='' --tb=short -q` | 7 PASS in 19.84s after deterministic red reproduction |
| Same Python command with `tests/test_mcp_http_transport.py tests/test_mcp_protocol_matrix.py tests/test_mcp_protocol_modernization.py` added | 42 PASS in 209.45s |
| `PYTHONPATH=src:sdk/python python -m pytest tests/test_sdk*.py tests/test_evaluation_benchmark_safety.py tests/test_web_platform.py tests/test_m13p4_inventory_read_contract.py tests/test_m13p_postgres_schema.py -o addopts='' --tb=short -q` | 364 PASS, 3 legacy-environment deprecation warnings, 61.12s |
| `PYTHONPATH=src python -m pytest tests/test_m13p4_acceptance_preflight.py -o addopts='' --tb=short -q` | 7 PASS; wrong/dirty/altered candidates refused; acceptance never executed |
| `ruff check tests/test_m13p4_*.py tests/test_mcp_wave1_compatibility.py scripts/engineering/m13p4_security_acceptance.py` | PASS |
| `ruff format --check` on the same paths | PASS |
| `git diff --check` | PASS |
| Diff from exact security baseline for `src/responsibleai/enterprise`, `isolation`, `mcp`, `db`, `tests/independent_m13r2`, `docs/security` | Empty |

`WHITEPACT_M13P4_MCP_REGRESSION_RESULTS.md` records the unchanged baseline failures and deterministic before/after checks. `WHITEPACT_M13P4_SDK_COMPATIBILITY.md` records 347 SDK/evaluation tests, 53 TypeScript tests, Go race/vet/build, isolated Python/TypeScript package installation, hashes and adapter coverage. The 364 integrated checks include overlapping SDK tests and must not be added to the 347 as distinct coverage.

## Browser evidence

`PYTHONPATH=src PLAYWRIGHT_BROWSERS_PATH=/Users/ag/Library/Caches/ms-playwright python -m pytest -q -s tests/test_m12p_live_public_browser.py tests/test_m13p4_browser_accessibility.py` initially passed both wrappers in 166.60s with two deprecated development-static-key warnings: 16 real PostgreSQL public/unauthenticated checks, plus 20 explicitly labeled UI fixture checks. The real public test performs no identity/root seeding. Browser fixtures block every API mutation and external origin. They do not establish customer authentication or authority.

The UI fixture harness was subsequently extended to audit the connected agent inventory, local pagination, no-match filtering and long identifiers at all three widths. Final command selected only `tests/test_m13p4_browser_accessibility.py` with the same environment: **1 passed, 1 development-key deprecation warning in 88.96s; 29 browser checks, zero axe violations, zero overflow and zero mutations**. The unchanged real public/unauthenticated 16-check result remains valid. Browser tests are wired into the new CI workflow on Python 3.11.

## Retries, failures and limitations

- Before correction, both named MCP tests passed alone; full product and observed exact-security-baseline runs reproduced incomplete chunked responses. The deterministic new regression failed twice before the fixture fix. No assertion was removed or weakened.
- The first integrated frontend run had 263 passes and one obsolete navigation expectation that Agents remained hidden. The expectation was updated to reflect the independently tested read-only route; the full 264-test run passed.
- An initial parent Python invocation incorrectly selected nonexistent `sdk/python/tests`; pytest exited 4 with no tests collected. The corrected repository test paths produced the 364-pass integrated result.
- A build during concurrent inventory implementation exposed nullable state typing; the inventory owner corrected it before final build/test evidence. Initial fixture/preflight Ruff findings were corrected before checks passed.
- The inventory backend test initially used the existing virtualenv's editable old checkout without `PYTHONPATH=src`; the corrected command targets this worktree. Session `last_seen_at` and request audit writes are standard bookkeeping, explicitly allowed by the read-only inventory assertion; authority/inventory writes remain prohibited.
- SDK adapter imports initially failed when the SDK source path was omitted. The corrected adapter run reports 39 PASS / 32 SKIP; optional OpenAI Agents, CrewAI and LlamaIndex dependencies are absent. ADK emits a deprecation warning. Skips remain unverified.
- Python package tooling and Go were initially unavailable; isolated temporary build dependencies and a checksum-verified official Go archive resolved those environmental blockers. No system toolchain or package publication was performed.
- Initial sandbox browser/socket attempts were refused. Approved loopback/Chromium runs completed. An exploratory Vite run lacked symlinked fonts; compiled-static browser runs loaded fonts successfully.
- Full backend suite, independent security acceptance, native Linux isolation qualification and the complete privileged customer golden journey were not executed here. Passing product CI cannot substitute for them.

## GitHub CI

`.github/workflows/m13p4-product-review.yml` adds console and Python 3.11/3.12 contract jobs, including real-TCP MCP lifecycle, ordinary tenant reads, preserved-schema migration, SDK tests, read-only preflight tests and local browser accessibility. It uses read-only repository permissions, pinned actions, disposable PostgreSQL and no deployment/secrets/OIDC step. The default job does not execute the independent concurrency/crash/security suite.

Final exact-head CI is checked after the last commit and recorded with full HEAD/tree/parent in the draft PR and final handoff. A running, skipped or failed job is not a pass; local results in this report are not presented as remote evidence.
