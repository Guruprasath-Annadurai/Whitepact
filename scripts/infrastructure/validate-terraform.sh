#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if ! command -v terraform >/dev/null 2>&1; then
  echo "BLOCKED_BY_MISSING_ACCESS: terraform CLI not installed"
  exit 2
fi

for env in development production; do
  echo "=== validate: environments/$env ==="
  (
    cd "infra/terraform/environments/$env"
    terraform init -backend=false -input=false >/dev/null
    terraform validate
    terraform fmt -check -recursive ../../modules
  )
done
echo "TESTED_IN_SIMULATION: terraform validate passed (no cloud apply)"
