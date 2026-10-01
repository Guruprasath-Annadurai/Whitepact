# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "infra/terraform/modules/whitepact-hetzner-foundation/templates/cloud-init-nftables.yaml"
)


def test_nftables_cloud_init_fail_closed_without_or_true() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "|| true" not in text
    assert "policy drop" in text
    assert 'include "/etc/nftables.d/whitepact-tier.nft"' in text
    assert "[systemctl, enable, nftables]" in text


def test_nftables_template_requires_successful_load() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "nft list table inet whitepact" in text
