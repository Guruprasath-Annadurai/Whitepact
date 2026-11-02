# OpenSSF `dynamic_analysis` — Branch Coverage Report

**Date**: 2026-08-17 (initial measurement), updated 2026-08-17 (later same day, after remediation)
**Tool**: `pytest` + `coverage.py` (via `pytest-cov`), the project's own automated test suite — OpenSSF's `dynamic_analysis` criterion accepts a fuzzer, a web application scanner, *or* an automated test suite with at least 80% branch coverage; this project uses the third path.

## Update: threshold reached

After the initial 72.82% measurement below, real tests (no exclusions, no skipped code) were added targeting the highest-missing-branch files: `billing/stripe_service.py` (0%→100%), `biasbuster/cli.py` (0%→100%), `db/eval_repository.py` (0%→100%), `dashboard/middleware.py` (25%→100%), `db/org_repository.py` (40%→100%), `eval/dataset_scanner.py` (71%→100%), `dashboard/config.py` (69%→92%), `dashboard/telemetry.py` (36%→100% functional, minor coverage.py one-liner-def artifacts remain), `auth/oidc.py` (38%→100%), and `dashboard/websocket_manager.py` (27%→100% functional).

```
Pure branch coverage:    80.19%  (1469/1832 branches)
Blended stmt+branch %:   ~89% (coverage.py's own default 'Cover' column -- still NOT the same metric, see below)
OpenSSF threshold:       80% (pure branch coverage)
THRESHOLD MET, with 2249/2249 tests passing (up from 2035 before this remediation pass).
```

New test files added: `tests/test_stripe_service.py`, `tests/test_cli.py`, `tests/test_eval_repository.py`, `tests/test_middleware.py`, `tests/test_org_repository.py`, `tests/test_dataset_scanner.py`, `tests/test_telemetry.py`, `tests/test_oidc.py`, `tests/test_websocket_manager.py`, plus additions to `tests/test_config.py`. Every test exercises real conditional branches in the target file — no `# pragma: no cover` exclusions were added to inflate the number.

`dashboard/app.py` (169 missing branches) and `mcp/tools.py` (65 missing branches) remain the largest sources of uncovered branches in the codebase and were deliberately left for a later pass — the 80% threshold was reached via the smaller, higher-value files first, consistent with the instruction to close the gap with legitimate tests rather than take the fastest path through the single largest file.

The initial (now-superseded) 72.82% measurement is preserved below for the record.

---

## The distinction that matters here

`coverage.py`'s own terminal report, with `--cov-branch` enabled, prints a **blended** "Cover" percentage:

```
percent_covered = (covered_lines + covered_branches) / (num_statements + num_branches)
```

That number for this codebase is **84.89%** — comfortably over 80%, and it is what `--cov-fail-under=80` in CI has always gated on. **This is not branch coverage.** OpenSSF's criterion asks specifically for:

```
branch_coverage = covered_branches / num_branches
```

isolated from statement coverage entirely. Reporting the blended 84.89% as "branch coverage" would have been a real, checkable overclaim — this document exists because that distinction was flagged before `dynamic_analysis` was marked MET on the strength of the wrong number.

## Command run

```bash
pytest -q --cov-branch \
  --cov=src/responsibleai --cov=src/biasbuster --cov=src/privacylabel \
  --cov-report=term-missing --cov-report=json
python scripts/check_branch_coverage.py
```

`scripts/check_branch_coverage.py` (new, this pass) reads `coverage.json`'s `totals.covered_branches`/`totals.num_branches` directly — the only place `coverage.py` exposes the pure branch numbers separately from the blended report.

## Result

```
Pure branch coverage:    72.82%  (1334/1832 branches)
Blended stmt+branch %:   84.89%  (coverage.py's own default 'Cover' column -- NOT the same metric)
OpenSSF threshold:       80% (pure branch coverage)
BELOW THRESHOLD by 7.18 points.
```

**2035/2035 tests pass** in this same run (no regressions, no exclusions used to inflate the number — this is the real figure against the current test suite, unmodified for this report).

## Where the gap is concentrated

The 15 files with the most uncovered branches (of 498 total missing branches across the codebase):

| Missing branches | Total branches | Covered | File |
|---|---|---|---|
| 169 | 356 | 53% | `dashboard/app.py` |
| 65 | 84 | 23% | `mcp/tools.py` |
| 34 | 34 | 0% | `biasbuster/cli.py` |
| 24 | 24 | 0% | `billing/stripe_service.py` |
| 16 | 22 | 27% | `dashboard/websocket_manager.py` |
| 15 | 32 | 53% | `privacylabel/deepfake/detector.py` |
| 15 | 24 | 38% | `auth/oidc.py` |
| 14 | 22 | 36% | `dashboard/telemetry.py` |
| 10 | 10 | 0% | `db/eval_repository.py` |
| 8 | 26 | 69% | `dashboard/config.py` |
| 8 | 60 | 87% | `mcp/server.py` |
| 7 | 24 | 71% | `eval/dataset_scanner.py` |
| 6 | 8 | 25% | `dashboard/middleware.py` |
| 6 | 10 | 40% | `db/org_repository.py` |
| 6 | 70 | 91% | `webhooks/manager.py` |

`dashboard/app.py`'s 169 missing branches alone are more than a third of the entire 498-branch gap — a single large file with many conditional response-building/error-handling paths, consistent with it being the FastAPI app's main entry point covering nearly every REST endpoint.

## What was done, and what was not

**Done, this pass**:
- `pyproject.toml`: `--cov-branch` and `--cov-report=json` added to `addopts`, permanently, so every local test run now produces real branch-coverage data by default.
- `scripts/check_branch_coverage.py`: computes and prints the real, isolated branch-coverage number, with an optional `--fail` flag for once the threshold is genuinely met.
- `.github/workflows/ci.yml`: CI now runs `--cov-branch`, produces `coverage.json`, and prints the real branch-coverage number on every run via a dedicated step — **not yet a hard-failing gate**, deliberately: setting `--fail` today would break CI on every future PR for a threshold this codebase does not yet meet, which is not the goal of visibility.

**Not done, honestly stated**: closing the 7.18-point gap itself. Per this task's own explicit instruction, that requires **legitimate new tests exercising the currently-uncovered conditional branches** in the files above — not excluding files from coverage measurement to raise the percentage artificially, which would be the wrong kind of fix and was not done. This is real, additional test-writing work concentrated in `dashboard/app.py` and `mcp/tools.py` primarily, not a quick fix — scoped as a separate, explicit follow-up rather than rushed here.

## Result

**Branch coverage (superseded by the update above): 72.82%**
**Criterion `dynamic_analysis` eligible for MET at that time: NO**

## Current result (see update section at top of document)

**Branch coverage: 80.19%** (1469/1832 branches, `coverage.json`'s `totals.covered_branches`/`totals.num_branches`)
**Criterion `dynamic_analysis` eligible for MET: YES** — real automated test suite, ≥80% pure branch coverage (not blended statement+branch coverage), 2249/2249 tests passing, CI enforces `--cov-branch` and reports the number on every run via `scripts/check_branch_coverage.py`.

`scripts/check_branch_coverage.py --fail` can now be enabled as a hard CI gate at 80% since the threshold is genuinely met; this was left informational-only during the remediation pass itself to avoid blocking mid-flight commits, and should be flipped on in a follow-up.
