# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Offline rehearsal records cannot be promoted to staging acceptance."""

from __future__ import annotations

from dataclasses import dataclass


class StagingAcceptanceRefusedError(RuntimeError):
    """An offline result was presented as a live staging pass."""


# Existing callers and tests catch this name. It is the same refusal.
StagingAcceptanceRefused = StagingAcceptanceRefusedError


@dataclass(frozen=True)
class AcceptanceRecord:
    suite: str
    scope: str
    passed: bool
    live_staging_accepted: bool = False

    def __post_init__(self) -> None:
        if self.scope not in {"offline", "staging"}:
            raise StagingAcceptanceRefused("Acceptance scope must be offline or staging.")
        if self.scope == "offline" and self.live_staging_accepted:
            raise StagingAcceptanceRefused("Offline test success is not staging acceptance.")
        if self.scope == "staging" and self.live_staging_accepted and not self.passed:
            raise StagingAcceptanceRefused("A failed live check cannot be accepted.")


def offline_record(suite: str, *, passed: bool) -> AcceptanceRecord:
    return AcceptanceRecord(
        suite=suite, scope="offline", passed=passed, live_staging_accepted=False
    )


def claim_staging_acceptance(record: AcceptanceRecord) -> None:
    """Live staging acceptance requires a staging-scoped record from a real host."""
    if record.scope != "staging" or not record.live_staging_accepted or not record.passed:
        raise StagingAcceptanceRefused(
            "Refusing staging acceptance. Offline or incomplete records stay NO-GO."
        )
