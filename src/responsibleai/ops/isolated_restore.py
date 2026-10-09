# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Isolated backup restore rehearsal. Never contacts R2 or a live database."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from responsibleai.ops.backup_crypto import encrypt_dump
from responsibleai.ops.r2_retention import BackupObject, plan_retention
from responsibleai.ops.restore_flow import (
    create_staging_sql,
    cutover_sql,
    drop_staging_sql,
    prepare_restore,
)

_DUMP = b"-- PostgreSQL database dump\nCREATE TABLE evidence (id int);\n"


@dataclass(frozen=True)
class RestoreRehearsal:
    scratch_database: str
    ciphertext_contains_secret: bool
    cutover_drops_active: bool
    retention_deletes_newest: bool
    scope: str = "offline"


def rehearse_isolated_restore(work_dir: Path, *, secret: str) -> RestoreRehearsal:
    """Encrypt, restore into a scratch name, and check retention inside work_dir."""
    if not secret or secret.strip() != secret or len(secret) < 16:
        raise ValueError("Rehearsal secret must be a single line of at least 16 characters.")
    work_dir.mkdir(parents=True, exist_ok=True)
    backup = work_dir / "rehearsal.sql.gz.enc"
    encrypt_dump(
        _DUMP,
        secret,
        backup,
        database="whitepact",
        tool_version="phase34-offline",
        required_relations=["evidence"],
    )
    ciphertext = backup.read_bytes()
    prepared = prepare_restore(backup, secret, work_dir / "scratch")
    active = "whitepact"
    previous = "whitepact_prev_rehearsal"
    first, second = cutover_sql(active, prepared.staging_database, previous)
    cutover = first + "\n" + second
    drop_sql = drop_staging_sql(prepared.staging_database)
    drops_active = "DROP" in cutover.upper() or active in drop_sql
    now = datetime(2026, 10, 9, tzinfo=UTC)
    objects = [
        BackupObject("newest", now - timedelta(days=1), True),
        BackupObject("middle", now - timedelta(days=10), True),
        BackupObject("oldest", now - timedelta(days=40), True),
        BackupObject("unviable", now - timedelta(days=2), False),
    ]
    plan = plan_retention(
        objects, now=now, retain_days=30, min_recovery_points=2, destructive=False
    )
    newest_deleted = "newest" in plan.delete
    return RestoreRehearsal(
        scratch_database=prepared.staging_database,
        ciphertext_contains_secret=secret.encode() in ciphertext,
        cutover_drops_active=drops_active,
        retention_deletes_newest=newest_deleted,
    )


def rehearsal_passes(result: RestoreRehearsal) -> bool:
    return (
        result.scope == "offline"
        and result.scratch_database.startswith("wp_restore_")
        and not result.ciphertext_contains_secret
        and not result.cutover_drops_active
        and not result.retention_deletes_newest
        and "CREATE DATABASE" in create_staging_sql(result.scratch_database, "whitepact")
    )
