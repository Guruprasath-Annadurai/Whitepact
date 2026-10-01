# CI pytest runtime (Launch Cell B)

## Symptom

GitHub Actions job `Lint · Type-check · Test` (`timeout-minutes: 45`) reached ~99% of pytest output then was **cancelled** when the job hit the limit. Coverage enforcement steps never ran.

## Root cause

1. **Stacked coverage configuration**: `pyproject.toml` `addopts` enables `--cov` on three packages plus `--cov-report=html`. The CI step added another `--cov=src/responsibleai` and `--cov-report=term-missing`, multiplying instrumentation and generating large HTML/terminal reports during teardown.
2. **Marginal test growth**: Cell B added real PostgreSQL and HTTP load tests (~1–2 minutes) on top of a suite that already completed in ~44 minutes on green SHA `9b6a7f2`.

## Fix

CI pytest now runs with `-o addopts=` (no HTML / `term-missing`) but keeps the same three-package `--cov` scope as `pyproject.toml` (`responsibleai`, `biasbuster`, `privacylabel`) so OpenSSF branch/statement gates are unchanged. Local developers keep full `pyproject.toml` addopts including HTML for offline review.

B9 HTTP load uses shorter burst/soak durations when `GITHUB_ACTIONS` is set; evidence remains `LOAD_TESTED` / `SOAK_TESTED`.

## Job timeout budget

GitHub Actions `timeout-minutes` for the Python matrix job is **55** (was 45). Evidence run `36418553498` @ `81c1e73` completed pytest in 26m (3.11) / 42m (3.12) with branch ≥80% and statement ≥90%; run `36424015014` @ `6346c70` hit the old 45m cap on a slow 3.11 runner (~43m pytest) despite passing branch coverage.
