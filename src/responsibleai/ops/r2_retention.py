# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""R2 backup retention. Dry-run unless destructive is explicit.

The newest viable recovery points are never selected for deletion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class BackupObject:
    key: str
    created_at: datetime
    viable: bool = True


@dataclass(frozen=True)
class RetentionPlan:
    delete: tuple[str, ...]
    keep: tuple[str, ...]
    dry_run: bool


def _aware(moment: datetime, tz_name: str) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("Timestamps must be timezone-aware.")
    return moment.astimezone(ZoneInfo(tz_name))


def plan_retention(
    objects: list[BackupObject],
    *,
    now: datetime,
    retain_days: int,
    min_recovery_points: int,
    tz_name: str = "UTC",
    destructive: bool = False,
) -> RetentionPlan:
    if retain_days < 1:
        raise ValueError("retain_days must be at least 1.")
    if min_recovery_points < 1:
        raise ValueError("min_recovery_points must be at least 1.")
    now_local = _aware(now, tz_name)
    cutoff = now_local - timedelta(days=retain_days)
    viable = [item for item in objects if item.viable]
    viable.sort(key=lambda item: _aware(item.created_at, tz_name), reverse=True)
    protected = {item.key for item in viable[:min_recovery_points]}
    delete: list[str] = []
    keep: list[str] = []
    for item in objects:
        created = _aware(item.created_at, tz_name)
        # Equality with the cutoff stays. Only strictly older objects are eligible.
        eligible = created < cutoff and item.key not in protected
        if eligible:
            delete.append(item.key)
        else:
            keep.append(item.key)
    if not destructive:
        return RetentionPlan(tuple(delete), tuple(keep), True)
    return RetentionPlan(tuple(delete), tuple(keep), False)


def utc_now() -> datetime:
    return datetime.now(UTC)
