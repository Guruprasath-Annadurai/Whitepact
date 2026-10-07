# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Restore planning that never names a drop of the active database."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from responsibleai.ops.backup_crypto import BackupRejectedError, decrypt_dump

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def quote_ident(name: str) -> str:
    if not _IDENT.fullmatch(name):
        raise BackupRejectedError("Database name is not a safe identifier.")
    return '"' + name + '"'


def new_staging_name() -> str:
    return "wp_restore_" + os.urandom(8).hex()


def new_previous_name(active: str) -> str:
    suffix = os.urandom(4).hex()
    candidate = f"{active}_prev_{suffix}"
    if _IDENT.fullmatch(candidate):
        return candidate
    return "wp_prev_" + suffix


@dataclass(frozen=True)
class PreparedRestore:
    plain_path: Path
    staging_database: str
    required_relations: tuple[str, ...]


def prepare_restore(backup: Path, secret: str, work_dir: Path) -> PreparedRestore:
    manifest_path = Path(str(backup) + ".manifest.json")
    plain, claims = decrypt_dump(backup, manifest_path, secret, work_dir)
    relations: list[str] = []
    for item in claims.required_relations:
        if not _IDENT.fullmatch(item):
            raise BackupRejectedError("Manifest required_relations contains an unsafe name.")
        relations.append(item)
    staging = new_staging_name()
    quote_ident(staging)
    return PreparedRestore(plain, staging, tuple(relations))


def create_staging_sql(staging: str, owner: str) -> str:
    return f"CREATE DATABASE {quote_ident(staging)} OWNER {quote_ident(owner)};"


def drop_staging_sql(staging: str) -> str:
    return f"DROP DATABASE IF EXISTS {quote_ident(staging)};"


def cutover_sql(active: str, staging: str, previous: str) -> tuple[str, str]:
    """Rename the verified staging database into place. Does not drop the active one."""
    first = f"ALTER DATABASE {quote_ident(active)} RENAME TO {quote_ident(previous)};"
    second = f"ALTER DATABASE {quote_ident(staging)} RENAME TO {quote_ident(active)};"
    return first, second


def relation_exists_sql(relation: str) -> str:
    quote_ident(relation)
    return f"SELECT to_regclass('public.{relation}') IS NOT NULL;"
