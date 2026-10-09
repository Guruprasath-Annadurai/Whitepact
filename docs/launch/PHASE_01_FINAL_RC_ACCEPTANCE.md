# Phase 1 — Final release-candidate acceptance

**Gate: CONDITIONAL.** GitHub Actions on exact SHA `0cdef3947503adf7c3f08a5116a4808deda1d3f7` completed green. That SHA is not a launch GO. Two defects confirmed on it are fixed only on the successor branch `cursor/whitepact-global-launch-execution-d20d`, which does not yet have its own GitHub Actions result.

## Source examined

| Item | Value |
|------|--------|
| `origin/main` | `38f927229b4ea53d19a9107c78653307f5263629` |
| PR #167 | https://github.com/Guruprasath-Annadurai/Whitepact/pull/167 |
| PR #167 HEAD | `0cdef3947503adf7c3f08a5116a4808deda1d3f7` |
| PR #167 tree | `b20ea9d9ab849f3d49ae51fa47ecfabc64b8f865` |
| Parent | `a5deaac6d74808983a407b28c6bc8f817e8bbcfa` |
| CI run | https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/37900487645 |
| CI conclusion | `success` (updated 2026-10-09T08:34:59Z) |
| Distribution name | `rai-governance-platform` |
| Declared version | `1.3.1` in `pyproject.toml` |
| Git tag `v1.3.1` | `894efe30514553f7e0d047a1569a80d36c53a236` (not this RC) |

PR #167 remains an open draft. It is not merged.

## Checks green on `0cdef394`

All of the following concluded success. None were still running when this record was written.

- Lint · Type-check · Test (3.11) — https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/37900487645/job/113721624990
- Lint · Type-check · Test (3.12) — https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/37900487645/job/113721625726
- Wheel install smoke (3.11) and (3.12)
- Frontend closure (lint · test · build · browser journey)
- i18n unit tests
- Accessibility (WCAG2AA)
- Helm chart lint
- Build distribution
- Rebuild artifacts identically — https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/37900487699
- dco-check — https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/37900487732
- dependency-review
- gitleaks
- CodeQL, CodeQL analysis (python), CodeQL analysis (javascript-typescript)
- Bandit SAST + pip-audit
- OpenSSF policy checks

## Coverage preserved

Thresholds were not changed.

| Interpreter | Pure branch (threshold 80) | Pure statement (threshold 90) | Blended stmt+branch |
|-------------|----------------------------|-------------------------------|---------------------|
| Python 3.11 | 80.90% (5763/7124) | 91.37% (26627/29141) | 89.31% |
| Python 3.12 | 81.27% (5790/7124) | 91.51% (26668/29141) | 89.50% |

Both jobs printed `At or above threshold` for the branch gate. The 3.11 statement gate printed the same. The 3.12 statement figure is 91.51% and that job succeeded.

## DCO

The workflow exception is exactly these two SHAs, recorded in `compliance/DCO_HISTORICAL_EXCEPTION_2026-10-09.md`:

- `015fab741427a5a9cae5bca7adaa9729c78da9e5`
- `681ce9566f0ef9b68b6fc97212cc2fb7a44135e3`

Local execution of `.github/workflows/dco.yml` via `tests/test_dco_historical_exception.py` rejected a new unsigned commit and accepted a signed commit. That test is part of the 61-test slice recorded for this successor. The exception text is not a `Signed-off-by` trailer.

## What this phase does not accept

- Docker image build is not a job on run `37900487645`. Image build was not executed in this session.
- Terraform `apply` and `plan` were not run. `terraform validate` on the three environment roots is recorded in Phase 3.
- Successor fixes are not on `0cdef394`, so that green run does not cover them.
- Antigravity has not qualified this successor. Cursor tests are not an independent PASS.
- PyPI publication was not performed.

## Install identity

Do not publish this candidate. From source, the declared project is:

```bash
pip install "rai-governance-platform[dashboard,postgres]"
```

That command installs the published distribution named `rai-governance-platform`, which is not proven to be commit `0cdef394`. The product command is `whitepact`. `pip install whitepact` is not the project name.

## Defects found after the green SHA

| ID | On `0cdef394` | Successor |
|----|----------------|-----------|
| WP-LAUNCH-P1-MEMORY-SCOPE-01 | Child `memory_scope` could widen during delegation | Fixed; retest required |
| WP-LAUNCH-P2-ACTION-PIN-01 | `- uses:` hid `actions/checkout@v4` from the pin checker | Fixed; retest required |

## Gate

CONDITIONAL. CI on `0cdef394` is complete and green. Launch acceptance is not, because those two defects exist on that SHA, the successor has no GitHub Actions result yet, and live staging, billing, legal, and independent qualification gates are open.
