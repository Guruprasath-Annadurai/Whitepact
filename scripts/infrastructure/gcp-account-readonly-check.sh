#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Read-only GCP account posture — no resource creation.
set -euo pipefail

if ! command -v gcloud >/dev/null 2>&1; then
  echo "BLOCKED_BY_MISSING_ACCESS: gcloud not installed"
  exit 2
fi

if ! gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -1 | grep -q .; then
  echo "OWNER_APPROVAL_REQUIRED: no active gcloud credentials"
  exit 2
fi

echo "=== Active account ==="
gcloud auth list --filter=status:ACTIVE

echo "=== Projects (names only) ==="
gcloud projects list --format='table(projectId,name)' 2>/dev/null || true

echo "=== Billing budgets (if permitted) ==="
gcloud billing budgets list 2>/dev/null || echo "BLOCKED_BY_MISSING_ACCESS: billing.budgets.list"

echo "VERIFIED: read-only check completed — credit balance must be confirmed in Cloud Console billing UI"
