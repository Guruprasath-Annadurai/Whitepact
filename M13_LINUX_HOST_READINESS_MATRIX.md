# Linux host readiness matrix

Probe format `WHITEPACT-M13-STAGE19-HOST-PROBE-V1`. The captured JSON is reproduced below because `*.json` evidence paths are gitignored.

```json
{
  "docker_daemon_id": "695d1154-d6ed-4b2b-bb03-a9c3572f47c3",
  "docker_reachable": true,
  "euid": 1000,
  "isolation_image": "python:3.11-slim",
  "isolation_image_digest": "python@sha256:673719e071ecf27434fd2635bbd8d00f49f4fdd81f243143438a42ced8bedf60",
  "kernel": "6.12.94+",
  "production_certified": false,
  "unisolated_execution_requested": false
}
```

| Requirement | This host | Result |
| --- | --- | --- |
| Linux kernel | `6.12.94+` x86_64 | Present. Not a production kernel pin |
| POSIX ACL tools | `/usr/bin/setfacl`, `/usr/bin/getfacl` | UID 65534 read succeeded, then failed after the ACE was removed |
| Workspace mode | owner-only plus ACL, other bits clear | Proved in `test_posix_acl_grants_container_uid_and_can_be_removed` |
| Docker daemon | `/usr/bin/docker`, API reachable, id `695d1154-d6ed-4b2b-bb03-a9c3572f47c3` | Reachable for this run only |
| Image provenance | `python:3.11-slim` at `sha256:673719e071ecf27434fd2635bbd8d00f49f4fdd81f243143438a42ced8bedf60` | Recorded. Not a signed production admission policy |
| Network restriction | `--network=none` | Workload connect to `1.1.1.1:443` failed and reported `denied` |
| PostgreSQL | local 16, revision `0067` | Durable containment row `CONTAINED` |
| Tenant | protected controller fixture | ACTIVE organization. TEST_ONLY, not Stage 17 provider proof |
| Unisolated flag | unset | Probe exits if `WHITEPACT_ALLOW_UNISOLATED_EXECUTION=1` |
| Teardown | ephemeral workspace and `--rm` container | Workspace gone after the ACL test; containment row retained |
| Missing prerequisite | before install, no docker and no setfacl | Qualification command exits non-zero. Not converted into a pass |

A green GitHub-hosted runner would prove that runner only. It would not certify a later production machine.

Command:

```bash
env -u WHITEPACT_ALLOW_UNISOLATED_EXECUTION \
  WHITEPACT_ISOLATION_IMAGE=python:3.11-slim \
  WHITEPACT_TEST_PG_ADMIN_URL=postgresql://wp:wp@127.0.0.1:5432/postgres \
  PYTHONPATH=src:. \
  python -m pytest tests/test_m13_stage19_linux_qualification.py -q --tb=short
```
