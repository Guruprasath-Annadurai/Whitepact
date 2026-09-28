#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# P1-B / P1-C — kind-based multi-replica load + Helm rollback (SELF_REHEARSED).
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

mkdir -p "$OUT_DIR"
exec > >(tee -a "$LOG") 2>&1

echo "=== Cell B kind qualification SHA=$SHA ==="

if ! command -v kind >/dev/null || ! command -v kubectl >/dev/null; then
  echo "ENVIRONMENT_BLOCKED: kind/kubectl not available"
  exit 2
fi

DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
  if sudo docker info >/dev/null 2>&1; then
    DOCKER="sudo docker"
  else
    echo "ENVIRONMENT_BLOCKED: docker daemon not accessible"
    python3 - <<PY
import json
from pathlib import Path
from datetime import datetime, UTC
sha="$SHA"
for name in ("b9-kind-http-load.json", "b10-kind-helm-rollback.json"):
    Path("${OUT_DIR}/"+name).write_text(json.dumps({
        "phase": name.split("-")[0].upper(),
        "status": "ENVIRONMENT_BLOCKED",
        "reason": "docker_socket_permission_denied",
        "source_sha": sha,
        "timestamp": datetime.now(UTC).isoformat(),
    }, indent=2)+"\\n")
PY
    exit 2
  fi
fi

kind delete cluster --name "$CLUSTER" 2>/dev/null || true
kind create cluster --name "$CLUSTER" --wait 300s

kubectl apply -f scripts/cell_b/k8s_kind_dependencies.yaml
kubectl -n "$NS" rollout status deployment/postgres --timeout=180s
kubectl -n "$NS" rollout status deployment/redis --timeout=180s

echo "Building application image..."
$DOCKER build -t "$IMAGE" -f Dockerfile .
kind load docker-image "$IMAGE" --name "$CLUSTER"

helm upgrade --install "$RELEASE" helm/rai-governance/ \
  --namespace "$NS" --create-namespace \
  -f helm/rai-governance/values-cell-b-kind.yaml \
  --set image.repository=whitepact-cell-b \
  --set image.tag=qual \
  --set image.pullPolicy=Never \
  --set config.databaseUrl="$DB_URL" \
  --set replicaCount=3 \
  --wait --timeout 600s

kubectl -n "$NS" get pods -l "app.kubernetes.io/name=rai-governance" -o wide
READY=$(kubectl -n "$NS" get deploy "$RELEASE" -o jsonpath='{.status.readyReplicas}')
echo "Ready replicas: $READY"

kubectl -n "$NS" port-forward "svc/${RELEASE}" 9876:8765 &
PF_PID=$!
sleep 5
BASE="http://127.0.0.1:9876"

for path in /livez /readyz /api/health; do
  curl -fsS "$BASE$path" >/dev/null
done

echo "Running HTTP load (disposable limits; not 4h/500 RPS enterprise gate)..."
LOAD_JSON="${OUT_DIR}/b9-kind-http-load.json"
python3 - <<'PY' "$BASE" "$LOAD_JSON"
import json, sys, threading, time, statistics
import httpx
base, out = sys.argv[1], sys.argv[2]
lat=[]; err=0; n=0
dead=time.monotonic()+60
lock=threading.Lock()
def w():
    global err,n
    c=httpx.Client(timeout=5)
    while time.monotonic()<dead:
        t=time.perf_counter()
        try:
            r=c.get(f"{base}/api/health")
            with lock:
                n+=1
                lat.append((time.perf_counter()-t)*1000)
                if r.status_code>=500: err+=1
        except httpx.HTTPError:
            with lock:
                err+=1; n+=1
    c.close()
threads=[threading.Thread(target=w) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()
lat.sort()
data={
  "phase":"B9",
  "environment":"kind_3_replicas_port_forward",
  "replica_count":3,
  "soak_seconds":60,
  "requests":n,
  "errors":err,
  "measured_rps":round(n/60,2),
  "measured_p95_ms":round(lat[int(len(lat)*0.95)-1],3) if lat else 0,
  "limitations":"Local kind cluster; not Antigravity 4h/500RPS staging target"
}
open(out,"w").write(json.dumps(data,indent=2)+"\n")
print(json.dumps(data,indent=2))
PY

echo "Introducing faulty release (broken database URL)..."
helm upgrade "$RELEASE" helm/rai-governance/ \
  --namespace "$NS" \
  -f helm/rai-governance/values-cell-b-kind.yaml \
  --set image.repository=whitepact-cell-b \
  --set image.tag=qual \
  --set image.pullPolicy=Never \
  --set config.databaseUrl="postgresql+asyncpg://wp:wp@postgres.cell-b-qual.svc.cluster.local:5432/invalid_db" \
  --set replicaCount=3 \
  --wait --timeout 180s || echo "Faulty release readiness failed as expected"

kubectl -n "$NS" wait --for=condition=ready pod -l "app.kubernetes.io/name=rai-governance" --timeout=30s || true
T_ROLLBACK=$(date -u +%FT%TZ)
helm rollback "$RELEASE" -n "$NS" --wait --timeout 300s
T_DONE=$(date -u +%FT%TZ)
sleep 5
curl -fsS "$BASE/readyz" >/dev/null

python3 - <<PY
import json
from pathlib import Path
out = Path("${OUT_DIR}/b10-kind-helm-rollback.json")
out.write_text(json.dumps({
  "phase": "B10",
  "method": "SELF_REHEARSED",
  "source_sha": "$SHA",
  "cluster": "kind",
  "namespace": "$NS",
  "release": "$RELEASE",
  "fault_injection": "invalid_database_url",
  "rollback_started_at": "$T_ROLLBACK",
  "rollback_finished_at": "$T_DONE",
  "transcript": "artifacts/production/kind-b9-b10-transcript.log",
  "post_rollback_readyz": "PASS",
  "limitations": "Disposable kind; not owner staging cluster"
}, indent=2) + "\\n")
PY

kill "$PF_PID" 2>/dev/null || true
echo "=== kind qualification complete ==="
