# Stage 19 evidence handoff for Antigravity

PR #240 is a draft. Do not treat it as independently qualified. Do not merge.

Candidate parent remains `a5a2fbfcfd17edb3459830ed0eff84003dfec42e`, tree `58756fd88cacf26163cd312c844959c62370edc7`. This note covers the successor commit on `cursor/m13-stage19-runtime-099e`.

## What changed

- Workspace teardown now checks the ephemeral directory returned by `EphemeralWorkspace.path`.
- Host qualification proves UID 65534 can read a file after `setfacl` and cannot read it after the ACE is removed.
- `DockerContainerBackend.execute` was run with the production trusted runner (`CONTAINER_RUNNER_SOURCE`) and image `whitepact-isolated-runtime:local`, built from `Dockerfile.isolation`. The containment probe was not enabled for that case.
- Network stayed disabled, the container user stayed 65534, and the PostgreSQL containment row ended `CONTAINED`.
- `digest_admission_enforced` is false. The local image id is `sha256:1962151b03fc2b86d0bb972d0326d9a2b0eaa6c247b143fb8073ae8926b8f5de`. Docker also lists that id in `RepoDigests` for the local tag. That is not a registry admission control, and none was added.

## Exact run

Command, from the branch, with `PYTHONPATH=src:.` and Docker group access:

```bash
WHITEPACT_TEST_PG_ADMIN_URL=postgresql://wp:wp@127.0.0.1:5432/postgres \
WHITEPACT_ISOLATION_IMAGE=python:3.11-slim \
WHITEPACT_TEST_RUNTIME_IMAGE=whitepact-isolated-runtime:local \
python -m pytest tests/test_m13_stage19_linux_qualification.py \
  tests/test_m13_execution_isolation_recovery.py::test_19_real_contained_execution \
  -q --tb=short --junitxml=junit.xml
```

| Python | Tests | Failures | Skips | Errors |
| --- | --- | --- | --- | --- |
| 3.12.3 | 6 | 0 | 0 | 0 |
| 3.11.11 | 6 | 0 | 0 | 0 |

JUnit receipts: `docs/engineering/m13-stage19/junit-3.12.xml` and `docs/engineering/m13-stage19/junit-3.11.xml`.

`test_19_real_contained_execution` ran. It was the case that previously skipped when `WHITEPACT_TEST_RUNTIME_IMAGE` was unset. No skip remains in this scoped run. The direct-permit receipt inside that test still says approval and nonce are not applicable. It is not a customer approval replay test.

Stage 17 did not pass. The canonical 25-stage journey did not pass.

M13 remains open. Production remains no-go. M14 is not authorized.
