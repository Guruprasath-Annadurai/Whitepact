# M13 Cursor I1 timeout root cause and evidence

Verdict: the two cancellations have an identified cause. Hosted proof that the new budgets finish the real ceremonies is recorded below only after the run on the commit that changes the workflow. M13 stays OPEN. Production is NO-GO. M14 is not authorized.

Starting SHA: `e42ef5d6a8bc615b876f56458e35e71c0c692bbc`.
Failed I1 run: `40301605603`
https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/40301605603

The identity gate is unchanged. `scripts/engineering/m13_apex_customer_journey.py` still exits 2 unless acceptance is `PASS`. The journey step does not use `continue-on-error`. No test is skipped, no synthetic credential is introduced, and historical DCO and Codex recovery files are untouched.

## What the failed run actually spent

Times are UTC on 26 Oct 2026. IST is UTC+5:30.

### Python 3.11 virtual authenticator

Job `121500583143` started 09:42:21Z (3:12 PM IST) and was cancelled at 09:55:08Z (3:25 PM IST). The job cap was 12 minutes.

| Step | Duration | Result |
|---|---|---|
| Checkout, Python, Node | under 10s | success |
| Install isolated browser component dependencies | 09:42:27Z–09:54:49Z, 12m22s | success, consumed the whole cap |
| Verify genuine browser ceremonies | 09:54:49Z–09:55:05Z, 16s | cancelled. Log: `The operation was canceled.` |
| Preserve component evidence | same second | failure. `No files were found` for `/tmp/m13-browser-component.xml` |

Inside the install step, pip finished at 09:42:56Z and npm ci at 09:43:01Z (`added 4 packages in 4s`). `npx playwright install --with-deps chromium` then ran apt. Archive indexes finished at 09:43:03Z. The next log line is `Setting up xfonts-scalable` at 09:54:38Z. Chrome for Testing 151.0.7922.34 started downloading at 09:54:41Z. The silent interval is apt installing Playwright system libraries, not pytest, not Chromium launch, and not an assertion hang. The ceremony was cancelled 16 seconds after it started, so it produced no JUnit file and no `coverage.json`.

The same workflow on Python 3.12, job `121500583215`, finished the whole job in 1m24s (09:42:21Z–09:43:45Z). Install was 46s (09:42:27Z–09:43:13Z). The ceremony step was 28s (09:43:13Z–09:43:41Z) and the evidence upload succeeded. The tests are not a 12-minute workload on a healthy runner.

### Customer journey

Job `121500583963` started 09:42:21Z and was cancelled at 09:57:21Z, exactly the 15-minute cap.

| Step | Duration | Result |
|---|---|---|
| Pip install | 09:42:38Z–09:43:04Z, 26s | success |
| Install real Chromium ceremony runtime | 09:43:07Z–09:56:14Z, 13m07s | success |
| Browser component, separate from the customer gate | 09:56:14Z–09:56:57Z, 43s | success |
| APEX 25-stage journey | 09:56:57Z–09:57:16Z, 19s | failure, process exit code 2 |
| Evidence upload | 09:57:16Z–09:57:18Z | success |

`POST /api/web/api-keys` returned 403 at 09:57:15Z (3:27 PM IST). The uploaded receipt is acceptance `BLOCKED`, stop `judgment`, 17 PASS / 1 BLOCKED / 7 NOT_EXECUTED / 0 FAIL, `IDENTITY_VERIFICATION_REQUIRED`, clean commit `e42ef5d6a8bc615b876f56458e35e71c0c692bbc`.

Checksums of that uploaded evidence:

```text
dde07588a7ee810ba8d43b9ba1f327c30e412116e8a55fa544f34f4957b10077  m13apex-customer-evidence.json
a45a186eadf3cb3c175be4d9c8bde0e9267067bbb9ac3b85b89fcde19061d799  m13i3-browser-evidence.json
```

The journey script had already exited 2. The job cap then cancelled the runner during teardown, so the job conclusion is `cancelled` rather than the step's exit 2. That is a budget collision, not a second customer-journey failure and not a pass.

## Root cause

Both jobs share one budget for Playwright's `install --with-deps` apt transaction and for the qualification commands. On a slow ubuntu-24.04 runner that apt transaction took 11m35s (authenticator) and the Chromium install step took 13m07s (journey). The 12-minute authenticator cap expired before assertions. The 15-minute journey cap expired at the same moment the identity-blocked script was finishing, so GitHub cancelled the job after the legitimate exit 2.

Python 3.12 on the same run shows the ceremonies themselves are short when apt is fast. This is runner apt variance, not a WebAuthn hang and not the identity gate.

## Fix

`.github/workflows/m13i1-integration.yml` only:

- `virtual-authenticator-component` and `real-customer-journey` `timeout-minutes` are 25. A hang still fails. The cap is no longer smaller than the observed apt stall.
- Each Chromium install is wrapped in `timeout 18m`. If apt or the browser download exceeds 18 minutes, that install step exits non-zero and the ceremonies do not start. That is a failed install, not a skipped test and not a green job.
- The install steps print `browser-install-start` and `browser-install-end` in UTC.
- The pytest commands, the journey command, coverage addopts, and `if-no-files-found: error` are unchanged. Exit 2 still fails `real-customer-journey`.

`tests/test_stage3_persona_sandbox.py::test_hosted_persona_step_has_explicit_disposable_pg16_target` and `tests/test_m13_pg16_test_runner.py` passed locally on Python 3.12.3 (4 tests). The pinned Persona and security step hashes were not edited.

## Hosted qualification

Not yet run on the commit that contains this budget change. Until that run finishes, both timeout remediations remain unproven on GitHub-hosted runners. A green authenticator job is proof only that the ceremonies and their artifacts completed. A `real-customer-journey` failure with exit 2 and acceptance `BLOCKED` is the required identity result, not a timeout cancellation and not acceptance `PASS`.
