#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Upload an encrypted Postgres backup to Cloudflare R2.
#
# Refuses plaintext .sql and .sql.gz. Does not upload the backup key.
#
# Required env: R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_ENDPOINT
# Usage: ./scripts/cloud/upload-backup-to-r2.sh /path/to/backup.sql.gz.enc

set -euo pipefail

BACKUP_FILE="${1:?backup file path required}"
R2_PREFIX="${R2_PREFIX:-whitepact/staging/postgres}"

PYTHON="${WHITEPACT_PYTHON:-python3}"
if ! "$PYTHON" -m responsibleai.ops upload-check --backup "$BACKUP_FILE" >/dev/null; then
  echo "ERROR: refusing to upload an artifact that is not an authenticated encrypted backup" >&2
  exit 2
fi

for var in R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_BUCKET R2_ENDPOINT; do
  if [ -z "${!var:-}" ]; then
    echo "ERROR: $var is not set" >&2
    exit 1
  fi
done

BASENAME="$(basename "$BACKUP_FILE")"
KEY="${R2_PREFIX}/${BASENAME}"
MANIFEST="${BACKUP_FILE}.manifest.json"
CHECKSUM="$(sha256sum "$BACKUP_FILE" | awk '{print $1}')"

export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="${R2_REGION:-auto}"

aws --endpoint-url "$R2_ENDPOINT" s3 cp "$BACKUP_FILE" "s3://${R2_BUCKET}/${KEY}"
aws --endpoint-url "$R2_ENDPOINT" s3 cp "$MANIFEST" "s3://${R2_BUCKET}/${KEY}.manifest.json"
echo "Uploaded encrypted object s3://${R2_BUCKET}/${KEY} sha256=${CHECKSUM}"
