#!/usr/bin/env bash
# SHA-256 checksums for DRAFT wheel/sdist when built locally — not final release.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST="${ROOT}/dist"
OUT="${ROOT}/artifacts/release-security/DRAFT-SHA256SUMS"
mkdir -p "$(dirname "${OUT}")"
if [[ ! -d "${DIST}" ]] || [[ -z "$(ls -A "${DIST}" 2>/dev/null)" ]]; then
  echo "No dist/ artifacts — run python -m build first" >&2
  exit 1
fi
(
  cd "${DIST}"
  sha256sum * > "${OUT}"
)
echo "Wrote ${OUT}"
