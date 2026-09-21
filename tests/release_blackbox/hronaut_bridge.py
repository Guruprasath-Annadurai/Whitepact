# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Minimal Hronaut-compatible bridge configuration (PREPARATION).

No public endpoint. No credentials. Ephemeral bridge config for later validation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HronautBridgeConfig:
    """Black-box topology: partner → HTTPS → staging tenant → UpstreamMCPExecutor."""

    public_only: bool = True
    allow_private_targets: bool = False
    staging_base_url: str = ""  # set only in controlled evaluation environment
    bridge_mcp_url: str = ""  # disposable target MCP — not production

    def validate(self) -> None:
        if self.allow_private_targets:
            raise ValueError("SSRF policy: private targets must not be enabled for PUBLIC_ONLY harness")
