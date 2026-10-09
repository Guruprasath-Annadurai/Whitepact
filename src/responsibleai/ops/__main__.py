# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Command helpers for the backup and restore shell scripts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from responsibleai.ops.backup_crypto import BackupRejectedError, assert_upload_allowed, encrypt_dump
from responsibleai.ops.restore_flow import prepare_restore

_SECRET_ENV = "WHITEPACT_BACKUP_ENCRYPTION_KEY"  # nosec B105 — environment variable name, not a key


def _secret() -> str:
    value = os.environ.get(_SECRET_ENV, "")
    if not value.strip():
        raise BackupRejectedError(f"{_SECRET_ENV} is not set.")
    return value


def _encrypt(args: argparse.Namespace) -> int:
    plain = Path(args.input).read_bytes()
    relations = [item for item in args.relation if item]
    encrypt_dump(
        plain,
        _secret(),
        Path(args.output),
        database=args.database,
        tool_version=args.tool_version,
        required_relations=relations,
    )
    print(f"encrypted {Path(args.output).name}")
    return 0


def _prepare(args: argparse.Namespace) -> int:
    prepared = prepare_restore(Path(args.backup), _secret(), Path(args.work))
    print(
        json.dumps(
            {
                "plain_path": str(prepared.plain_path),
                "staging_database": prepared.staging_database,
                "required_relations": list(prepared.required_relations),
            }
        )
    )
    return 0


def _upload_check(args: argparse.Namespace) -> int:
    manifest = assert_upload_allowed(Path(args.backup))
    print(manifest.name)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="whitepact-backup")
    sub = parser.add_subparsers(dest="cmd", required=True)
    enc = sub.add_parser("encrypt")
    enc.add_argument("--input", required=True)
    enc.add_argument("--output", required=True)
    enc.add_argument("--database", required=True)
    enc.add_argument("--tool-version", default="1.3.1")
    enc.add_argument("--relation", action="append", default=[])
    enc.set_defaults(func=_encrypt)
    prep = sub.add_parser("prepare-restore")
    prep.add_argument("--backup", required=True)
    prep.add_argument("--work", required=True)
    prep.set_defaults(func=_prepare)
    upload = sub.add_parser("upload-check")
    upload.add_argument("--backup", required=True)
    upload.set_defaults(func=_upload_check)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BackupRejectedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
