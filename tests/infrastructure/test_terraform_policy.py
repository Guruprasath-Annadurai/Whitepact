# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FOUNDATION = REPO / "infra/terraform/modules/whitepact-hetzner-foundation"


def test_hcloud_provider_source_is_hetznercloud() -> None:
    text = (FOUNDATION / "versions.tf").read_text(encoding="utf-8")
    assert "hetznercloud/hcloud" in text
    assert "hashicorp/hcloud" not in text


def test_network_zone_not_location_suffix() -> None:
    main = (FOUNDATION / "main.tf").read_text(encoding="utf-8")
    assert "${var.location}-network" not in main
    assert "local.network_zone" in main


def test_execution_egress_fail_closed_in_module() -> None:
    main = (FOUNDATION / "main.tf").read_text(encoding="utf-8")
    assert '"0.0.0.0/0"' not in main or "fail closed" in main
    assert "execution_egress_cidrs" in (FOUNDATION / "variables.tf").read_text(encoding="utf-8")


def test_saas_public_ipv4_disabled_by_default() -> None:
    variables = (FOUNDATION / "variables.tf").read_text(encoding="utf-8")
    assert "saas_public_ipv4" in variables
    assert "default     = false" in variables.split("saas_public_ipv4")[1][:200]
