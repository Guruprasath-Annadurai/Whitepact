# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveryBudget:
    max_sources: int = 5
    max_requests: int = 8
    max_redirects: int = 3
    max_response_bytes: int = 512_000
    max_discovery_seconds: float = 20.0
    max_relationship_depth: int = 2


DEFAULT_DISCOVERY_BUDGET = DiscoveryBudget()
