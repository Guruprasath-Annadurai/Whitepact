# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 plan-only cloud / origin static invariants (no terraform apply)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TF = ROOT / "infra" / "terraform"


def test_hetzner_nftables_default_drop_policy() -> None:
    template = (
        TF / "modules" / "whitepact-hetzner-foundation" / "templates" / "cloud-init-nftables.yaml"
    )
    text = template.read_text(encoding="utf-8")
    assert "policy drop" in text
    assert "chain forward" in text


def test_cloudflare_edge_module_present() -> None:
    assert (TF / "modules" / "cloudflare-edge" / "main.tf").is_file()


def test_mcp_forwarded_ip_not_trusted_by_default() -> None:
    server = (ROOT / "src" / "responsibleai" / "mcp" / "server.py").read_text(encoding="utf-8")
    assert "trust_forwarded" in server
    assert "_env_bool" in server
