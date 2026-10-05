# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Static checks for cloud staging plan (no terraform apply)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOUD = ROOT / "docs" / "enterprise" / "cloud"
QUALIFIED_M6 = "ee6e4a26becf7e89a933202651fba3b4e7a8176d"

REQUIRED_DOCS: tuple[str, ...] = (
    "CLOUD_STAGING_COST_AND_RESOURCE_PLAN.md",
    "CLOUD_STAGING_TOPOLOGY.md",
    "CLOUD_NETWORK_TRUST_BOUNDARY.md",
    "CLOUD_ORIGIN_PROTECTION.md",
    "CLOUD_SECRET_INVENTORY.md",
    "CLOUD_BACKUP_AND_RESTORE_EVIDENCE.md",
    "CLOUD_OBSERVABILITY_AND_ALERTING.md",
    "CLOUD_DEPLOYMENT_EVIDENCE.md",
    "CLOUD_STAGING_KNOWN_LIMITATIONS.md",
    "CLOUD_ANTIGRAVITY_HANDOFF.md",
)


def test_cloud_staging_docs_present() -> None:
    for name in REQUIRED_DOCS:
        assert (CLOUD / name).is_file(), name


def test_cloud_cost_plan_requires_owner_gate() -> None:
    text = (CLOUD / "CLOUD_STAGING_COST_AND_RESOURCE_PLAN.md").read_text(encoding="utf-8")
    assert "APPROVE STAGING CLOUD PROVISIONING" in text
    assert QUALIFIED_M6 in text or "ee6e4a2" in text


def test_staging_terraform_root_present() -> None:
    staging = ROOT / "infra" / "terraform" / "environments" / "staging"
    assert (staging / "main.tf").is_file()


def test_upload_backup_script_has_spdx() -> None:
    script = (ROOT / "scripts" / "cloud" / "upload-backup-to-r2.sh").read_text(encoding="utf-8")
    assert "SPDX-License-Identifier" in script
