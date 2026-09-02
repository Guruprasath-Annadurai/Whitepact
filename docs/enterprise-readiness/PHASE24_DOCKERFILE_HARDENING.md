# Phase 24 — Dockerfile / Container Hardening Verification

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH
CLOSURE MASTER DIRECTIVE, Phase 24. `00_MASTER_READINESS_AUDIT.md`'s
Deployment row flagged this as unverified — not re-derived from first
principles, flagged for direct inspection.

## What was actually inspected (not assumed)

### Non-root — confirmed, already correct

```
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/sh --create-home appuser
...
USER appuser
```

The runtime image genuinely runs as `appuser` (uid 1001), not root —
`USER` is set before `CMD`, after all `RUN` steps needing root
(package install, directory creation) are done.

### Minimal base — confirmed

`python:3.12-slim`, both build and runtime stages; multi-stage build
(`AS builder` / `AS runtime`) so the final image never carries the
`build` toolchain (`pip install --upgrade pip build`, the wheel build
step) — only the installed wheel and its runtime dependencies. `apt-get`
installs exactly one extra package (`curl`, needed for the
`HEALTHCHECK`) and cleans `/var/lib/apt/lists/*` in the same layer.

### Pinned base image — was NOT pinned, now fixed

Both `FROM python:3.12-slim` lines used a **mutable tag**, not a
digest — the same tag can point at different bytes over time (a new
`3.12-slim` build, e.g. after a Debian security patch). Fixed: pinned
to the tag's current multi-arch manifest-list digest
(`sha256:e5c9fa26ffb76e11e0f054f30dc2523a2f9693f0c36c0cf1e39b27e152d899fc`,
resolved via `docker buildx imagetools inspect python:3.12-slim`) —
this is the *index* digest, not a single-platform manifest digest, so
`docker build` still resolves the correct `linux/amd64`/`linux/arm64`
image per builder platform; only the tag's own mutability is closed.
Re-pinning to a newer digest is a deliberate, reviewable action from
here on, not an automatic silent drift.

### Healthcheck — confirmed, already correct

Real `HEALTHCHECK` instruction hitting `/api/health` and asserting the
JSON `status` field is `healthy` or `degraded`, not just a bare port
check.

### Read-only filesystem / capability dropping — was NOT set anywhere, now added

The Dockerfile itself has no opinion on this (correctly — read-only
root filesystem is an orchestration-time flag, not a Dockerfile
directive). Confirmed by direct inspection: `docker-compose.prod.yml`
set none of `read_only`, `cap_drop`, or `security_opt` for either
application service (`dashboard`, `mcp-http`) before this phase.

**Added to both services**:
```yaml
read_only: true
tmpfs:
  - /tmp
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
```

`/tmp` is mounted as tmpfs (writable, but not persisted or part of the
image layer) since Python/uvicorn commonly need *some* writable
scratch space even when the application's own persistent state lives
in Postgres, not the container filesystem — confirmed this compose
file's app services use `RAI_DATABASE_URL` (Postgres), not the
SQLite-file `/data` path the base Dockerfile's `ENV RAI_DB_PATH`
default implies, so no other writable mount was added.

**Named honestly — verification scope**: `docker compose -f
docker-compose.prod.yml config` was used to confirm these directives
parse and normalize correctly (real command, real output, captured
below) — this environment has no running Docker daemon, so an actual
`docker compose up` smoke test against the hardened config was **not**
performed. If the real deployment hits a read-only-filesystem write
error at startup, the fix is an additional `tmpfs:` entry for whatever
path fails, not reverting `read_only: true` wholesale. Recommended
before the first real production rollout of this change: bring the
stack up in a disposable environment and confirm the dashboard/MCP-HTTP
services actually start clean.

```
$ POSTGRES_PASSWORD=x REDIS_PASSWORD=y docker compose -f docker-compose.prod.yml config
...
    cap_drop:
      - ALL
    read_only: true
    security_opt:
      - no-new-privileges:true
    tmpfs:
      - /tmp
...
```

(repeated identically for the `mcp-http` service — full output
confirmed valid YAML both before and after via `python3 -c "import
yaml; yaml.safe_load(...)"`)

## Resource limits — not added, named as a gap

No `deploy.resources.limits` (cpus/memory) exist for either service.
Not added in this phase — a memory/CPU ceiling needs real capacity
data from Phase 13's load testing (or better, production traffic) to
set sensibly rather than guessed; guessing a wrong limit risks
OOM-killing a healthy process under legitimate load. Recorded as a
follow-up, not silently added with an arbitrary number.

## Phase 24 verdict

**READY TO ADVANCE.** Non-root and minimal-base were already correct
and are now independently confirmed rather than assumed. Base-image
pinning and container hardening (read-only root, capability dropping,
no-new-privileges) were genuinely missing and are now added — the one
caveat is that the hardening changes have not been smoke-tested
against a live container in this environment, stated plainly rather
than claimed as fully verified.
