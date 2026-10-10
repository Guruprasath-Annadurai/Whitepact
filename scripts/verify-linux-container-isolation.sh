#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Run the real container-isolation tests on a Linux kernel, from macOS or Linux.
#
# Why this exists: Docker Desktop on macOS shares host files through a layer that ignores
# host owner/mode bits, so permission bugs that break every container on Linux (for
# example a 0o400 runner the container UID cannot read) pass silently on a Mac, and the
# isolation tests there can only record a QUALIFICATION_SKIP. This script runs the same
# tests inside a Linux container that drives the Docker daemon, with workspaces on the
# VM's own ext4 volume so the kernel enforces real DAC, as it does on a CI runner.
#
#   scripts/verify-linux-container-isolation.sh            # as root (chown mapping path)
#   scripts/verify-linux-container-isolation.sh nonroot    # uid 1001 + POSIX ACLs (CI path)
#   scripts/verify-linux-container-isolation.sh nonroot tests/test_runner_immutability.py
#
# It tests the COMMITTED tree (git archive HEAD), not uncommitted edits. Not a substitute
# for CI on x86_64 Ubuntu: it uses Docker Desktop's VM kernel and this machine's CPU arch.
set -euo pipefail

MODE="${1:-root}"
[[ "$MODE" == "root" || "$MODE" == "nonroot" ]] && shift || MODE="root"
TESTS=("$@")
if [[ ${#TESTS[@]} -eq 0 ]]; then
  TESTS=(
    tests/test_docker_ownership_regression.py
    tests/test_docker_container_lifecycle.py
    tests/test_runtime_isolation_docker.py
    tests/test_runtime_isolation_hardgate.py
    tests/test_runtime_isolation_stress.py
    tests/test_isolation_workspace_permissions.py
    tests/test_runner_immutability.py
    tests/test_isolation_real_tool_e2e.py
  )
fi

cd "$(git rev-parse --show-toplevel)"
export WHITEPACT_REQUIRE_DOCKER_ISOLATION=1

if [[ "$(uname -s)" == "Linux" ]]; then
  echo "Native Linux: running the tests directly."
  exec python -m pytest -o addopts= -q -p no:cacheprovider "${TESTS[@]}"
fi

docker info >/dev/null 2>&1 || { echo "Docker daemon is not reachable." >&2; exit 2; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
VOLUME="wp-isolation-verify"
VM_PATH="/var/lib/docker/volumes/${VOLUME}/_data"

docker volume create "$VOLUME" >/dev/null
# A static Linux docker client for the verification container to drive the host daemon.
docker rm -f wp-cli-extract >/dev/null 2>&1 || true
docker create --name wp-cli-extract docker:cli >/dev/null
docker cp wp-cli-extract:/usr/local/bin/docker "$WORK/docker"
docker rm wp-cli-extract >/dev/null
mkdir -p "$WORK/src"
git archive HEAD | tar -x -C "$WORK/src"

# The runtime image the isolated tests execute real tools in (see Dockerfile.isolation).
RUNTIME_IMAGE="whitepact-isolated-runtime:verify"
docker build -q -f "$WORK/src/Dockerfile.isolation" -t "$RUNTIME_IMAGE" "$WORK/src" >/dev/null

cat >"$WORK/inner.sh" <<'INNER'
#!/bin/bash
set -uo pipefail
VM_PATH="$1"; MODE="$2"; shift 2
mkdir -p "$VM_PATH/tmp"
cp -r /src /work
echo "== kernel: $(uname -sr) arch: $(uname -m) mode: $MODE"
if [[ "$MODE" == "nonroot" ]]; then
  apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq acl >/dev/null 2>&1
  GID=$(stat -c %g /var/run/docker.sock)
  getent group "$GID" >/dev/null || groupadd -g "$GID" dockersock
  useradd -m -u 1001 -G "$GID" runner
  chown -R runner "$VM_PATH/tmp"
fi
cd /work && pip install -q -e ".[dev,dashboard]" >/tmp/pip.log 2>&1 || { tail -5 /tmp/pip.log; exit 3; }
if [[ "$MODE" == "nonroot" ]]; then
  chown -R runner /work
  exec runuser -u runner -- env TMPDIR="$VM_PATH/tmp" WHITEPACT_REQUIRE_DOCKER_ISOLATION=1 \
    WHITEPACT_TEST_RUNTIME_IMAGE="$WHITEPACT_TEST_RUNTIME_IMAGE" \
    PYTHONWARNINGS=ignore python -m pytest -o addopts= -q -p no:cacheprovider "$@"
fi
export TMPDIR="$VM_PATH/tmp" PYTHONWARNINGS=ignore
exec python -m pytest -o addopts= -q -p no:cacheprovider "$@"
INNER

docker run --rm \
  -e WHITEPACT_TEST_RUNTIME_IMAGE="$RUNTIME_IMAGE" -e WHITEPACT_REQUIRE_DOCKER_ISOLATION=1 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$WORK/docker":/usr/local/bin/docker:ro \
  -v "$VM_PATH":"$VM_PATH" \
  -v "$WORK/src":/src:ro \
  -v "$WORK/inner.sh":/inner.sh:ro \
  python:3.11-slim bash /inner.sh "$VM_PATH" "$MODE" "${TESTS[@]}"
