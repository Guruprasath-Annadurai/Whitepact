# Qualification skip policy

A skip is not a pass. Linux security CI fails when `nft`, `ip`,
`setfacl`, `nginx`, `openssl`, or `curl` is missing. Other platforms
skip those controls through `tests/linux_security.py` with the prefix
`QUALIFICATION_SKIP`.

Record a run with:

```bash
WHITEPACT_QUALIFICATION_SKIP_LOG=docs/launch/evidence/qualification-skips.json \
  pytest -o addopts= tests/test_runner_immutability.py \
  tests/test_isolation_workspace_permissions.py \
  tests/test_foundation_hardening.py tests/test_phase34_origin_aop.py
```

On the Linux host used for this candidate, with Docker not running and
without `WHITEPACT_REDIS_URL`, the recorded skips were:

- foreign UID probe after ACL grant, because Docker or root is required
- container UID read after ACL grant, because the Docker daemon is down
- fail-closed ACL path, because this host can grant the container UID
- live Redis window, because that invocation did not set `WHITEPACT_REDIS_URL`

A separate invocation with Redis on `127.0.0.1:6379` and
`WHITEPACT_REQUIRE_REDIS=1` passed
`test_live_redis_replicas_share_a_window`. That is two clients, one
Redis process, one machine. It is not a multi-host production proof.

Real `setfacl` and the nftables namespace test ran on this host. They
were not stubbed.
