#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Wait until the dashboard health endpoint responds (terminals may start in parallel).
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:8765/api/health" >/dev/null 2>&1; then
    echo "Dashboard is healthy on port 8765"
    exit 0
  fi
  sleep 1
done

echo "Dashboard did not become healthy within 60s (uvicorn terminal may still be starting)"
exit 0
