#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source .venv/bin/activate

if curl -fsS "http://127.0.0.1:8765/api/health" >/dev/null 2>&1; then
  echo "Dashboard already running on port 8765"
  exit 0
fi

mkdir -p /tmp/whitepact
nohup env RAI_AUTH_ENABLED=false RAI_DB_PATH=:memory: \
  uvicorn responsibleai.dashboard.app:app \
  --host 0.0.0.0 --port 8765 \
  > /tmp/whitepact/dashboard.log 2>&1 &
echo $! > /tmp/whitepact/dashboard.pid

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:8765/api/health" >/dev/null 2>&1; then
    echo "Dashboard is healthy on port 8765"
    exit 0
  fi
  sleep 1
done

echo "Dashboard failed to become healthy; see /tmp/whitepact/dashboard.log"
exit 1
