#!/usr/bin/env bash
# Free automated vulnerability scan via OWASP ZAP baseline scan.
#
# This is NOT a substitute for a paid third-party penetration test — it's
# an automated scanner, not a human adversary. Disclose it as exactly that:
# "automated OWASP ZAP baseline scan," never as "penetration test."
#
# Usage:
#   ./scripts/security-scan.sh <target_url>
#   ./scripts/security-scan.sh https://api.yourcompany.com
#   ./scripts/security-scan.sh http://localhost:8765   # against a local dev instance
#
# Requires Docker (uses the official zaproxy/zap-stable image — nothing
# installed on your machine beyond Docker itself).
#
# Output: reports/zap-baseline-<timestamp>.html and .json in the repo root.
# Exit code: 0 if no issues, 1 if warnings, 2 if failures (per ZAP's own
# convention) — treat 2 as blocking, 1 as review-before-shipping.

set -euo pipefail

TARGET_URL="${1:?Usage: $0 <target_url>}"
OUTPUT_DIR="${OUTPUT_DIR:-./reports}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_HTML="zap-baseline-${TIMESTAMP}.html"
REPORT_JSON="zap-baseline-${TIMESTAMP}.json"

if ! command -v docker &> /dev/null; then
  echo "ERROR: Docker is required. Install: https://docs.docker.com/get-docker/" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "[$(date -u +%FT%TZ)] Running OWASP ZAP baseline scan against ${TARGET_URL}"
echo "This is an automated scan — not a substitute for a paid third-party pentest."
echo ""

# zap-baseline.py runs a passive scan (safe against production — it does not
# attempt exploitation, only spiders and inspects responses). For a more
# thorough (but riskier, don't run against production) active scan, use
# zap-full-scan.py instead — see https://www.zaproxy.org/docs/docker/full-scan/
#
# ZAP exits 1 (warnings) or 2 (failures) on findings by design — `set -e`
# would abort the script right here before the pass/warn/fail reporting
# below ever ran, so this command is deliberately exempted from it.
set +e
docker run --rm \
  -v "$(pwd)/${OUTPUT_DIR}:/zap/wrk/:rw" \
  --network host \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py \
  -t "$TARGET_URL" \
  -r "$REPORT_HTML" \
  -J "$REPORT_JSON" \
  -I
EXIT_CODE=$?
set -e

echo ""
echo "[$(date -u +%FT%TZ)] Scan complete."
echo "  HTML report: ${OUTPUT_DIR}/${REPORT_HTML}"
echo "  JSON report: ${OUTPUT_DIR}/${REPORT_JSON}"

if [ "$EXIT_CODE" -eq 0 ]; then
  echo "  Result: PASS — no issues found."
elif [ "$EXIT_CODE" -eq 1 ]; then
  echo "  Result: WARNINGS — review the report before treating this as clean."
else
  echo "  Result: FAILURES — do not disclose this scan as clean; fix findings first."
fi

echo ""
echo "To publish alongside CAIQ_SELF_ASSESSMENT.md, copy the HTML report into"
echo "compliance/scan-reports/ and link it — never fabricate or paraphrase"
echo "scan results without the underlying report attached."

exit "$EXIT_CODE"
