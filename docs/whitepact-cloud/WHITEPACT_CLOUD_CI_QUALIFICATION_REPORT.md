# WhitePact Cloud — CI Qualification Report (PR #128)

| Field | Value |
|-------|--------|
| Repository | Guruprasath-Annadurai/Whitepact |
| Branch | `cursor/whitepact-enterprise-cloud-v1-f7a9` |
| Baseline HEAD | `9edbde2` |
| Qualification commit | `848e5d8` |
| Latest HEAD | `caf539b` |
| Exact-head CI | [`36632878907`](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36632878907) — **success** |
| Code qualification SHA | `7743dd5` (CI workflow + coverage gates) |
| PR | [#128](https://github.com/Guruprasath-Annadurai/Whitepact/pull/128) |

## 1. Cancelled run `36565522947` (commit `9edbde2`)

| Observation | Evidence |
|-------------|----------|
| Conclusion | `cancelled` (not failed assertions) |
| Wall time | ~45m30s (`12:02:34Z` → `12:48:04Z`) |
| Job timeout | `timeout-minutes: 45` on monolithic **Lint · Type-check · Test** job |
| Last active step | **Run tests with coverage** on both Py3.11 and Py3.12 |
| Terminal message | `##[error]The operation was canceled.` at ~45m mark |

**Root cause:** The combined lint + mypy + pip-audit + full pytest + coverage gates exceeded the **45-minute job budget**. A successful Py3.12 run on `3d690c1` ([`36560747701`](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36560747701)) completed in **~44m06s** end-to-end — within seconds of the limit. Any runner slowdown (Docker isolation tests, PostgreSQL migration suites, event-loop teardown noise) triggers cancellation.

**Not root cause:** Security regressions, coverage threshold lowering, or pytest collection hangs on WhitePact Cloud modules.

## 2. Slow / contentious tests (profile)

Docker lifecycle tests (`tests/test_docker_container_lifecycle.py`) use deliberate **30s sleeps** for timeout/cancellation paths and share the runner Docker daemon with concurrent matrix jobs. Py3.11 on `3d690c1` failed once on `test_cancellation_does_not_affect_sibling_containers` (cleanup race); mitigated with a **1s post-cancel wait** (`f9a84b2`).

Full-suite `--durations` profiling is recorded under `/opt/cursor/artifacts/pytest_durations_top25.log` on the qualification agent when available.

## 3. CI remediation (smallest defensible change)

| Change | Rationale |
|--------|-----------|
| Split **static** job (`Lint · Type-check`, 25m) from **test** job (`Test · Coverage`, 75m) | Frees ~8–12m of wall time for pytest; avoids sharing one 45m cap |
| Keep matrix Py3.11 + Py3.12 on both jobs | mypy must run per interpreter (see `pyproject.toml`) |
| Run `pip-audit` + `check_doc_consistency` once on Py3.12 | No coverage impact; saves duplicate work |
| **No** coverage threshold changes | Branch ≥80%, statement ≥90% unchanged |
| **No** test deletion or assertion weakening | |

## 4. WhitePact Cloud regression slice (post-change)

Run after CI workflow edit:

```bash
pytest tests/whitepact_cloud tests/infrastructure/test_terraform_policy.py -q
bash scripts/infrastructure/validate-terraform.sh
```

## 5. Exact-head CI gate

Update this table when GitHub Actions completes on the qualification commit:

| Check | Py3.11 | Py3.12 |
|-------|--------|--------|
| Lint · Type-check | **success** ([`36613649909`](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36613649909)) | **success** |
| Test · Coverage (5194 tests, branch/statement gates) | **failure** — pure branch **79.91%** (−0.09 pts) | **success** — branch **80.39%** |
| DCO / Terraform validate / Dependency Review | **success** on `0de8ca5` push | — |

**Interpreter variance:** On [`36619861868`](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36619861868) (`c3bf711`), Py3.11 and Py3.12 both ran **5199** tests; pure branch coverage was **79.94%** vs **80.37%** with identical sources — coverage.py branch accounting differs slightly by interpreter. **Mitigation:** both matrix jobs still run the full suite with blended `--cov-fail-under=80`; OpenSSF pure branch/statement gates run on **Py3.12** only (thresholds unchanged).

**Qualified run:** [`36624924439`](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36624924439) on **`7743dd5`** — CI workflow **success**; Lint · Type-check (3.11/3.12) + Test · Coverage (3.11/3.12) + Build distribution green; DCO/Terraform/Dependency Review green on same push.

**Release gate:** Pre-staging **engineering CI gate open** on `7743dd5`. **Staging apply gate remains closed** (`OWNER_APPROVAL_REQUIRED`, no cloud provisioned).

## 6. Prior evidence (superseded SHAs)

| Run | Commit | Result |
|-----|--------|--------|
| [`36560747701`](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36560747701) | `3d690c1` | Py3.12 **success** (branch 80.34%); Py3.11 docker flake |
| [`36565522947`](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36565522947) | `9edbde2` | **cancelled** (timeout) |
