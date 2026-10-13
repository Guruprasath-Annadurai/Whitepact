#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Upload a Postgres backup artifact to Cloudflare R2 (S3-compatible API).
#
# Required env (never commit):
#   R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_ENDPOINT
# Optional: R2_PREFIX (default whitepact/staging/postgres)
#
# Usage: ./scripts/cloud/upload-backup-to-r2.sh /path/to/backup.sql.gz

set -euo pipefail

BACKUP_FILE="${1:?backup file path required}"
R2_PREFIX="${R2_PREFIX:-whitepact/staging/postgres}"

for var in R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_BUCKET R2_ENDPOINT; do
  if [ -z "${!var:-}" ]; then
    echo "ERROR: $var is not set" >&2
    exit 1
  fi
done

if [ ! -s "$BACKUP_FILE" ]; then
  echo "ERROR: backup file missing or empty: $BACKUP_FILE" >&2
  exit 1
fi

BASENAME="$(basename "$BACKUP_FILE")"
KEY="${R2_PREFIX}/${BASENAME}"
CHECKSUM="$(sha256sum "$BACKUP_FILE" | awk '{print $1}')"
MANIFEST="$(mktemp)"
trap 'rm -f "$MANIFEST"' EXIT

cat >"$MANIFEST" <<EOF
{"object":"$KEY","sha256":"$CHECKSUM","uploaded_at":"$(date -u +%FT%TZ)","source":"whitepact-backup"}
EOF

export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="${R2_REGION:-auto}"

aws --endpoint-url "$R2_ENDPOINT" s3 cp "$BACKUP_FILE" "s3://${R2_BUCKET}/${KEY}"
aws --endpoint-url "$R2_ENDPOINT" s3 cp "$MANIFEST" "s3://${R2_BUCKET}/${KEY}.manifest.json"

echo "Uploaded s3://${R2_BUCKET}/${KEY} sha256=${CHECKSUM}"
