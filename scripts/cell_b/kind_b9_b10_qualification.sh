#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# P1-B / P1-C — kind-based distributed load + Helm rollback (SELF_REHEARSED).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
OUT_DIR="${ROOT}/artifacts/production"
LOG="${OUT_DIR}/kind-b9-b10-transcript.log"
SHA="$(git rev-parse HEAD)"
CLUSTER="whitepact-cell-b"
NS="cell-b-qual"
RELEASE="rai-cell-b"
IMAGE="whitepact-cell-b:qual"
DB_URL="postgresql+asyncpg://wp:wp@postgres.cell-b-qual.svc.cluster.local:5432/whitepact"
LOAD_DURATION="${CELL_B_B9_DURATION:-120}"
LOAD_WORKERS="${CELL_B_B9_WORKERS:-8}"

mkdir -p "$OUT_DIR"
exec > >(tee -a "$LOG") 2>&1

block_artifacts() {
  local reason="$1"
  python3 - <<PY
import json
from pathlib import Path
from datetime import datetime, UTC
sha="$SHA"
reason="$reason"
for name, phase in (("b9-kind-http-load.json", "B9"), ("b10-kind-helm-rollback.json", "B10")):
    Path("${OUT_DIR}/"+name).write_text(json.dumps({
        "phase": phase,
        "status": "ENVIRONMENT_BLOCKED",
        "reason": reason,
        "source_sha": sha,
        "timestamp": datetime.now(UTC).isoformat(),
        "diagnostics": "artifacts/production/kind-bootstrap-diagnostics.json",
    }, indent=2)+"\\n")
PY
}

echo "=== Cell B kind qualification SHA=$SHA ==="

if ! command -v kind >/dev/null || ! command -v kubectl >/dev/null || ! command -v helm >/dev/null; then
  echo "ENVIRONMENT_BLOCKED: kind/kubectl/helm not available"
  block_artifacts "missing_kubernetes_tooling"
  exit 2
fi

DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
  if sudo docker info >/dev/null 2>&1; then
    DOCKER="sudo docker"
  else
    echo "ENVIRONMENT_BLOCKED: docker daemon not accessible"
    block_artifacts "docker_socket_permission_denied"
    exit 2
  fi
fi

bash scripts/cell_b/kind_bootstrap_diagnostics.sh || {
  block_artifacts "kind_control_plane_bootstrap_failed"
  exit 2
}

KIND="kind"
if [[ "$DOCKER" == "sudo docker" ]]; then KIND="sudo kind"; fi
$KIND delete cluster --name "$CLUSTER" 2>/dev/null || true
if ! $KIND create cluster --name "$CLUSTER" --wait 300s; then
  block_artifacts "kubeadm_wait_control_plane"
  exit 2
fi

kubectl apply -f scripts/cell_b/k8s_kind_dependencies.yaml
kubectl -n "$NS" rollout status deployment/postgres --timeout=180s
kubectl -n "$NS" rollout status deployment/redis --timeout=180s

echo "Building application image..."
$DOCKER build -t "$IMAGE" -f Dockerfile .
$KIND load docker-image "$IMAGE" --name "$CLUSTER"

helm upgrade --install "$RELEASE" helm/rai-governance/ \
  --namespace "$NS" --create-namespace \
  -f helm/rai-governance/values-cell-b-kind.yaml \
  --set image.repository=whitepact-cell-b \
  --set image.tag=qual \
  --set image.pullPolicy=Never \
  --set config.databaseUrl="$DB_URL" \
  --set replicaCount=3 \
  --set-json 'extraEnv=[{"name":"WHITEPACT_INSTANCE_ID","valueFrom":{"fieldRef":{"fieldPath":"metadata.name"}}}]' \
  --wait --timeout 600s

kubectl -n "$NS" get pods -l "app.kubernetes.io/name=rai-governance" -o wide
READY=$(kubectl -n "$NS" get deploy "$RELEASE" -o jsonpath='{.status.readyReplicas}')
DESIRED=$(kubectl -n "$NS" get deploy "$RELEASE" -o jsonpath='{.spec.replicas}')
echo "Ready replicas: $READY / $DESIRED"

kubectl -n "$NS" create configmap cell-b-b9-load-script \
  --from-file=b9_in_cluster_load.py=scripts/cell_b/b9_in_cluster_load.py \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f scripts/cell_b/k8s_b9_load_job.yaml
kubectl -n "$NS" wait --for=condition=complete job/cell-b-b9-load --timeout=900s
kubectl -n "$NS" cp "$(kubectl -n "$NS" get pod -l job-name=cell-b-b9-load -o jsonpath='{.items[0].metadata.name}')":/tmp/b9-load.json \
  "${OUT_DIR}/b9-kind-http-load.json" || true

python3 - <<PY
import json
from pathlib import Path
p = Path("${OUT_DIR}/b9-kind-http-load.json")
if p.exists():
    data = json.loads(p.read_text())
    data["source_sha"] = "$SHA"
    data["status"] = "SELF_REHEARSED" if data.get("distinct_replicas_observed", 0) >= 2 else "FAILED_DISTRIBUTION"
    data["ready_replicas"] = int("$READY" or 0)
    data["desired_replicas"] = int("$DESIRED" or 0)
    data["environment"] = "kind_in_cluster_service_load"
    data["transcript"] = "artifacts/production/kind-b9-b10-transcript.log"
    p.write_text(json.dumps(data, indent=2) + "\\n")
PY

GOOD_REV=$(helm history "$RELEASE" -n "$NS" --max 1 -o json | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['revision'])")
GOOD_IMAGE=$(kubectl -n "$NS" get deploy "$RELEASE" -o jsonpath='{.spec.template.spec.containers[0].image}')
T_FAULT_START=$(date -u +%FT%TZ)

echo "Functional check before fault (in-cluster)..."
kubectl -n "$NS" run cell-b-pre-check --rm -i --restart=Never --image=curlimages/curl:8.5.0 -- \
  curl -fsS "http://${RELEASE}.${NS}.svc.cluster.local:8765/readyz" >/dev/null

echo "Introducing faulty release (broken database URL)..."
set +e
helm upgrade "$RELEASE" helm/rai-governance/ \
  --namespace "$NS" \
  -f helm/rai-governance/values-cell-b-kind.yaml \
  --set image.repository=whitepact-cell-b \
  --set image.tag=qual \
  --set image.pullPolicy=Never \
  --set config.databaseUrl="postgresql+asyncpg://wp:wp@postgres.cell-b-qual.svc.cluster.local:5432/invalid_db" \
  --set replicaCount=3 \
  --set-json 'extraEnv=[{"name":"WHITEPACT_INSTANCE_ID","valueFrom":{"fieldRef":{"fieldPath":"metadata.name"}}}]' \
  --wait --timeout 180s
FAULT_RC=$?
set -e
T_FAULT_END=$(date -u +%FT%TZ)
kubectl -n "$NS" get pods -l "app.kubernetes.io/name=rai-governance" -o wide || true
kubectl -n "$NS" get events --sort-by=.lastTimestamp | tail -n 20 || true

BAD_REV=$(helm history "$RELEASE" -n "$NS" --max 1 -o json | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['revision'])")

T_ROLLBACK=$(date -u +%FT%TZ)
helm rollback "$RELEASE" "$GOOD_REV" -n "$NS" --wait --timeout 300s
T_DONE=$(date -u +%FT%TZ)
ROLL_REV=$(helm history "$RELEASE" -n "$NS" --max 1 -o json | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['revision'])")

kubectl -n "$NS" run cell-b-post-check --rm -i --restart=Never --image=curlimages/curl:8.5.0 -- \
  curl -fsS "http://${RELEASE}.${NS}.svc.cluster.local:8765/readyz" >/dev/null

python3 - <<PY
import json
from pathlib import Path
hist = __import__("subprocess").check_output(
    ["helm", "history", "$RELEASE", "-n", "$NS", "-o", "json"], text=True
)
out = Path("${OUT_DIR}/b10-kind-helm-rollback.json")
out.write_text(json.dumps({
  "phase": "B10",
  "method": "SELF_REHEARSED",
  "status": "SELF_REHEARSED",
  "source_sha": "$SHA",
  "cluster": "kind",
  "namespace": "$NS",
  "release": "$RELEASE",
  "known_good_helm_revision": int("$GOOD_REV"),
  "known_good_image": "$GOOD_IMAGE",
  "fault_injection": "invalid_database_url",
  "fault_helm_upgrade_exit_code": int("$FAULT_RC"),
  "fault_detected_at": "$T_FAULT_END",
  "post_fault_helm_revision": int("$BAD_REV"),
  "rollback_target_revision": int("$GOOD_REV"),
  "rollback_started_at": "$T_ROLLBACK",
  "rollback_finished_at": "$T_DONE",
  "post_rollback_helm_revision": int("$ROLL_REV"),
  "helm_history": json.loads(hist),
  "transcript": "artifacts/production/kind-b9-b10-transcript.log",
  "post_rollback_readyz": "PASS",
  "limitations": "Disposable kind; not owner staging cluster",
}, indent=2) + "\\n")
PY

echo "=== kind qualification complete ==="
