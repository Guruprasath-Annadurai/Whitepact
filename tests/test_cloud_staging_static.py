# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Static checks for cloud staging plan (no terraform apply)."""

from __future__ import annotations

import re
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


def test_staging_plan_documents_nat_not_tier_hcloud_firewall() -> None:
    text = (CLOUD / "CLOUD_HOST_FIREWALL_POLICY.md").read_text(encoding="utf-8")
    assert "nftables" in text
    main = (
        ROOT / "infra" / "terraform" / "modules" / "whitepact-hetzner-foundation" / "main.tf"
    ).read_text(encoding="utf-8")
    assert "hcloud_firewall.nat_gateway" in main
    assert "hcloud_firewall.authority" not in main


def test_cloud_cost_plan_requires_owner_gate() -> None:
    text = (CLOUD / "CLOUD_STAGING_COST_AND_RESOURCE_PLAN.md").read_text(encoding="utf-8")
    assert "APPROVE STAGING CLOUD PROVISIONING" in text
    assert QUALIFIED_M6 in text or "ee6e4a2" in text


_TF_ASSIGNMENT = re.compile(
    r"""(?m)^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*("[^"]*"|[^\s#]+)"""
)


def _tf_assignments(text: str) -> dict[str, str]:
    """Read HCL attribute assignments without depending on alignment spaces."""
    values: dict[str, str] = {}
    for name, raw in _TF_ASSIGNMENT.findall(text):
        values[name] = raw.strip().strip('"')
    return values


def test_lb_service_protocol_ignores_alignment_whitespace() -> None:
    compact = 'lb_service_protocol="tcp"\n'
    aligned = '  lb_service_protocol      = "tcp"\n'
    padded = 'lb_service_protocol   =   "tcp"\n'
    assert _tf_assignments(compact)["lb_service_protocol"] == "tcp"
    assert _tf_assignments(aligned)["lb_service_protocol"] == "tcp"
    assert _tf_assignments(padded)["lb_service_protocol"] == "tcp"


def test_staging_terraform_root_present() -> None:
    staging = ROOT / "infra" / "terraform" / "environments" / "staging"
    assert (staging / "main.tf").is_file()
    values = _tf_assignments((staging / "main.tf").read_text(encoding="utf-8"))
    assert values.get("lb_service_protocol") == "tcp"
    assert values.get("lb_listen_port") == "443"


def test_upload_backup_script_has_spdx() -> None:
    script = (ROOT / "scripts" / "cloud" / "upload-backup-to-r2.sh").read_text(encoding="utf-8")
    assert "SPDX-License-Identifier" in script
