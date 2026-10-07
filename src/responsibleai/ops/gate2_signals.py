# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Gate 2 signal evaluation. A met condition is not a claim that a pager fired."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SignalSnapshot:
    backup_age_hours: float | None
    backup_failed: bool
    restore_drill_failed: bool
    origin_tls_failed: bool
    disk_used_percent: float | None
    db_connected: bool | None
    application_healthy: bool | None
    execution_healthy: bool | None


def evaluate(
    snapshot: SignalSnapshot, *, backup_age_limit_hours: float = 26, disk_limit_percent: float = 85
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(signal: str, met: bool, detail: str, runbook: str) -> None:
        findings.append(
            {
                "signal": signal,
                "condition_met": met,
                "detail": detail,
                "runbook": runbook,
                "alert_dispatched": False,
            }
        )

    if snapshot.backup_age_hours is None:
        add(
            "backup_age",
            True,
            "No backup timestamp was supplied.",
            "GATE2_STAGING_RUNBOOK.md#backup",
        )
    elif snapshot.backup_age_hours > backup_age_limit_hours:
        add(
            "backup_age",
            True,
            f"Newest backup is {snapshot.backup_age_hours:.1f}h old.",
            "GATE2_STAGING_RUNBOOK.md#backup",
        )
    else:
        add(
            "backup_age",
            False,
            "Backup age is inside the window.",
            "GATE2_STAGING_RUNBOOK.md#backup",
        )
    add(
        "backup_failure",
        snapshot.backup_failed,
        "Last backup attempt failed." if snapshot.backup_failed else "No backup failure flag.",
        "GATE2_STAGING_RUNBOOK.md#backup",
    )
    add(
        "restore_drill_failure",
        snapshot.restore_drill_failed,
        "Restore drill failed."
        if snapshot.restore_drill_failed
        else "No restore-drill failure flag.",
        "GATE2_STAGING_RUNBOOK.md#drill",
    )
    add(
        "origin_tls_failure",
        snapshot.origin_tls_failed,
        "Origin TLS check failed." if snapshot.origin_tls_failed else "No origin TLS failure flag.",
        "CLOUD_ORIGIN_PROTECTION.md",
    )
    disk_met = (
        snapshot.disk_used_percent is not None and snapshot.disk_used_percent >= disk_limit_percent
    )
    add(
        "disk_threshold",
        disk_met,
        "Disk usage is at or over the threshold."
        if disk_met
        else "Disk usage is under the threshold.",
        "CLOUD_OBSERVABILITY_AND_ALERTING.md",
    )
    add(
        "db_connectivity",
        snapshot.db_connected is False,
        "Database connectivity check failed."
        if snapshot.db_connected is False
        else "Database connectivity was ok or not checked.",
        "GATE2_STAGING_RUNBOOK.md#backup",
    )
    add(
        "application_health",
        snapshot.application_healthy is False,
        "Application health check failed."
        if snapshot.application_healthy is False
        else "Application health was ok or not checked.",
        "CLOUD_OBSERVABILITY_AND_ALERTING.md",
    )
    add(
        "execution_service_health",
        snapshot.execution_healthy is False,
        "Execution service health check failed."
        if snapshot.execution_healthy is False
        else "Execution health was ok or not checked.",
        "CLOUD_OBSERVABILITY_AND_ALERTING.md",
    )
    return findings
