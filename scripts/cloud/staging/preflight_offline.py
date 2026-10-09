#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Offline staging preflight. Does not apply Terraform, change DNS, or read secret values."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from responsibleai.ops.staging_cost import (  # noqa: E402
    STAGING_CEILING_CENTS,
    assess_spend,
    optional_backup_eur,
    staging_lines,
    staging_monthly_cents,
)
from responsibleai.ops.staging_rollout import plan_deploy, plan_health, plan_rollback  # noqa: E402
from responsibleai.ops.staging_scope import offline_record  # noqa: E402
from responsibleai.ops.staging_secrets import blocked_names, review_staging_secrets  # noqa: E402
from responsibleai.ops.staging_static import OWNER_DEPENDENCIES, isolation_defects  # noqa: E402


def main() -> int:
    defects = isolation_defects()
    cents = staging_monthly_cents()
    alert = assess_spend(cents, STAGING_CEILING_CENTS)
    secret_report = review_staging_secrets({})
    record = offline_record("phase34-preflight", passed=not defects and cents == STAGING_CEILING_CENTS)
    deploy = plan_deploy("a" * 40, "APPROVE_STAGING_CLOUD_PROVISIONING")
    report = {
        "scope": record.scope,
        "live_staging_accepted": record.live_staging_accepted,
        "terraform_apply": deploy["terraform_apply"],
        "defects": list(defects),
        "monthly_eur_ex_vat": f"{cents / 100:.2f}",
        "ceiling_eur_ex_vat": f"{STAGING_CEILING_CENTS / 100:.2f}",
        "lines": [
            {"name": line.name, "sku": line.sku, "eur_ex_vat": f"{line.monthly_cents / 100:.2f}"}
            for line in staging_lines()
        ],
        "optional_server_backups_eur_ex_vat": optional_backup_eur(),
        "spend_alert": {
            "severity": alert.severity,
            "blocks_apply": alert.blocks_apply,
            "action": alert.action,
        },
        "secrets_missing_in_this_process": list(blocked_names(secret_report)),
        "health": plan_health(None),
        "rollback_execute": plan_rollback("b" * 40, "c" * 40)["execute"],
        "owner_dependencies": [{"id": item_id, "need": need} for item_id, need in OWNER_DEPENDENCIES],
    }
    print(json.dumps(report, indent=2))
    if defects or cents != STAGING_CEILING_CENTS or alert.blocks_apply or deploy["terraform_apply"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
