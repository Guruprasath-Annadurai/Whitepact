#!/usr/bin/env bash
# Generate DRAFT CycloneDX SBOM from current tree — NOT the final release artifact.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${ROOT}/artifacts/release-security/DRAFT-cyclonedx-sbom.json"
mkdir -p "$(dirname "${OUT}")"
SHA="$(git -C "${ROOT}" rev-parse HEAD)"
python3 -m pip install -q cyclonedx-bom pip-audit 2>/dev/null || true
if ! python3 -m cyclonedx_py 2>/dev/null; then
  echo "Install: pip install cyclonedx-bom" >&2
  exit 1
fi
cyclonedx-py environment \
  --output-format JSON \
  --output-file "${OUT}" \
  --spec-version 1.6
echo "DRAFT SBOM at ${OUT} (git ${SHA}) — not final release"
