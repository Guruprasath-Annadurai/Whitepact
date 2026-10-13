#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${ROOT}/artifacts/production/kind-bootstrap-diagnostics.json"
SHA="$(git -C "$ROOT" rev-parse HEAD)"
TS="$(date -u +%FT%TZ)"
mkdir -p "$(dirname "$OUT")"
LOG="${ROOT}/artifacts/production/kind-bootstrap-diagnostics.log"
exec > >(tee -a "$LOG") 2>&1

DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
  if sudo docker info >/dev/null 2>&1; then DOCKER="sudo docker"; fi
fi

CLUSTER="whitepact-cell-b-diag"
FAIL_REASON=""
KUBEADM_SNIP=""

echo "=== kind bootstrap diagnostics SHA=$SHA ==="
echo "docker: $($DOCKER version --format '{{.Server.Version}}' 2>/dev/null || echo unavailable)"
free -h || true
df -h / /var/lib/docker 2>/dev/null || df -h /
sysctl fs.inotify.max_user_instances 2>/dev/null || true

if ! command -v kind >/dev/null; then
  FAIL_REASON="kind_binary_missing"
else
  kind delete cluster --name "$CLUSTER" 2>/dev/null || true
  if [[ "$DOCKER" == "sudo docker" ]]; then
    export DOCKER_HOST=unix:///var/run/docker.sock
  fi
  KIND_CREATE=(kind create cluster --name "$CLUSTER" --wait 300s)
  if [[ "$DOCKER" == "sudo docker" ]]; then
    KIND_CREATE=(sudo -E kind create cluster --name "$CLUSTER" --wait 300s)
  fi
  if ! "${KIND_CREATE[@]}" 2> "${ROOT}/artifacts/production/kind-create.stderr"; then
    FAIL_REASON="kind_create_failed"
    KUBEADM_SNIP="$(tail -n 40 "${ROOT}/artifacts/production/kind-create.stderr" 2>/dev/null || true)"
    $DOCKER logs "${CLUSTER}-control-plane" 2>/dev/null | tail -n 80 || true
    journalctl -u kubelet --no-pager -n 40 2>/dev/null || true
  else
    kubectl cluster-info || true
    kubectl get nodes -o wide || true
    if [[ "$DOCKER" == "sudo docker" ]]; then sudo kind delete cluster --name "$CLUSTER" || true; else kind delete cluster --name "$CLUSTER" || true; fi
  fi
fi

python3 - <<PY
import json
from pathlib import Path
Path("$OUT").write_text(json.dumps({
  "phase": "B9_B10",
  "test": "kind_bootstrap_diagnostics",
  "source_sha": "$SHA",
  "timestamp": "$TS",
  "status": "PASS" if not "$FAIL_REASON" else "ENVIRONMENT_BLOCKED",
  "failure_reason": "$FAIL_REASON" or None,
  "kubeadm_tail": """$KUBEADM_SNIP""".strip() or None,
  "transcript": "artifacts/production/kind-bootstrap-diagnostics.log",
}, indent=2) + "\\n")
PY

if [[ -n "$FAIL_REASON" ]]; then exit 2; fi
