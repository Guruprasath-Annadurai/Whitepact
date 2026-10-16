#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Forge stage journal around the actual I3 PostgreSQL/HTTP/browser ceremony."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from scripts.engineering.m13i3_browser_journey import attempt, validate_report


def stage_journal(evidence: dict) -> dict:
    """Preserve the original evidence; never upgrade a partial ceremony to PASS."""
    validate_report(evidence)
    stages = []
    names = set()
    for phase in evidence["phases"]:
        names.add(phase["phase"])
        stages.append({**phase, "status": "PASS" if phase["result"] == "CONFIRMED" else "BLOCKED"})
    for name in evidence["not_executed"]:
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("Unexecuted stage duplicates or contradicts executed evidence")
        names.add(name)
        stages.append({"phase": name, "status": "NOT EXECUTED"})
    blocked = [item["phase"] for item in stages if item["status"] == "BLOCKED"]
    if not blocked and evidence.get("stop") == "DOWNSTREAM_AUTHORITY_CONTRACTS_NOT_QUALIFIED":
        if not any(
            item["phase"] == "server_assertion_verification" and item["status"] == "PASS"
            for item in stages
        ):
            raise ValueError("Downstream boundary lacks actual assertion verification")
        boundary = "downstream_authority_qualification"
        stages.append({"phase": boundary, "status": "BLOCKED", "reason": evidence["stop"]})
        blocked = [boundary]
    if not blocked:
        raise ValueError("Incomplete journey has no explicit blocking stage")
    return {
        "schema": "whitepact.forge.customer-journey.v1",
        "acceptance": "BLOCKED",
        "first_blocked_stage": blocked[0],
        "stages": stages,
        "original_evidence": evidence,
        "production": "GLOBAL PRODUCTION NO-GO",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    try:
        journal = stage_journal(asyncio.run(attempt()))
    except Exception as error:
        # A harness failure is distinct from an observed customer contract blocker.
        journal = {
            "schema": "whitepact.forge.customer-journey.v1",
            "acceptance": "FAIL",
            "stages": [{"phase": "harness", "status": "FAIL"}],
            "error_type": type(error).__name__,
            "production": "GLOBAL PRODUCTION NO-GO",
        }
    args.report.write_text(json.dumps(journal, indent=2) + "\n")
    raise SystemExit(2)
