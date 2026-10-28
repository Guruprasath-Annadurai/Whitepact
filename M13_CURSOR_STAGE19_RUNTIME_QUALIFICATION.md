# M13 Stage 19 runtime qualification

Source candidate: `a5a2fbfcfd17edb3459830ed0eff84003dfec42e`.
Tree: `58756fd88cacf26163cd312c844959c62370edc7`.
Parent: `8116664f04b41fbf16042ad1282c4e402812926e`.
Qualification-only workflow commit `94756f5b0a0b66d4bb3d8407160f6ee3bcf90434` was not edited. PR #239 was not changed. Codex branches were not checked out.

Worktree: `/tmp/m13-stage19` on `cursor/m13-stage19-runtime-099e`, created clean from the candidate. Working tree was empty before these files.

## Root cause

The canonical journey cannot complete a default isolated execution on a host that lacks a reachable Docker daemon or working POSIX ACLs. That is the intended fail-closed contract, not an authorization bug.

| Observation | Class |
| --- | --- |
| `IsolationBroker` refuses unisolated execution unless an explicit local prototype flag is set | Software enforcement, left unchanged |
| Missing `setfacl` on a non-root host raises `IsolationFilesystemPermissionError` and the recovery tests record CONSUMED approval, zero nonce, BLOCKED outcome | Missing Linux prerequisite, already fail-closed |
| Docker daemon absent returns backend unavailable before nonce admission | Missing host prerequisite |
| Docker Desktop / WSL2 bind mounts cannot prove host DAC or UID 65534 ACLs | Existing `require_container_isolation_host` skip on non-Linux. This host is native Linux, so that skip does not apply |
| Existing reconstruction tests mock the broker | Test harness. They are not containment proof. The file says so |
| HTTP 503 after a proven preflight refusal | Legitimate denial. Not redesigned |
| Stage 17 provider assurance | Still required for a customer 25/25. This work does not fabricate it |

This cloud host started without `setfacl` and without `dockerd`. Both were installed from Ubuntu packages for this qualification only. No paid infrastructure was created.

## What was verified

PostgreSQL 16, schema `0067`, protected disposable tenant (TEST_ONLY, email-verified fixture, not a provider identity), real `DockerContainerBackend.execute`:

- image `python:3.11-slim` digest `python@sha256:673719e071ecf27434fd2635bbd8d00f49f4fdd81f243143438a42ced8bedf60`
- daemon id `695d1154-d6ed-4b2b-bb03-a9c3572f47c3`, Docker 29.1.3, kernel `6.12.94+`, euid 1000
- container user 65534, `--network=none`, `--cap-drop=ALL`
- workload result `{"marker":"TEST_ONLY","network":"denied"}`
- `runtime_containment_records.state` became `CONTAINED`
- POSIX ACL `user:nobody:r--` on a 0700/non-world-readable workspace, then the workspace was removed
- `WHITEPACT_ALLOW_UNISOLATED_EXECUTION` was unset and the probe refuses if it is set

Python 3.12.3: `tests/test_m13_stage19_linux_qualification.py` — 4 passed.
Python 3.11: that file plus `tests/test_m13_execution_isolation_recovery.py` — 24 passed, 1 skipped. The skip is the existing native-containment case inside the reconstruction file, which stays skipped unless the designated CI flag is set. It is not a pass.

Option A behavior was not redesigned. Stage 17 was not modified.

M13 remains open. This host is not a production certificate. Production remains no-go.
