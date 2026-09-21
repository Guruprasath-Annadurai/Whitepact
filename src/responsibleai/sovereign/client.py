# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Python SDK for Sovereign — in-process client (safe read/simulate)."""

from __future__ import annotations

from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.protocol import SovereignCapabilities, SovereignStatus
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.sources import SovereignCanonicalStore

# Retry classification for HTTP consumers (in-process client does not auto-retry).
RETRY_SAFE_READS = frozenset({"status", "capabilities", "xray", "explain", "trace"})
RETRY_NEVER_BLIND = frozenset(
    {"shadow", "simulate", "gauntlet", "capsule_reproduce", "grant", "execute"}
)


class SovereignClient:
    def __init__(
        self,
        store: SovereignCanonicalStore | None = None,
        capabilities: SovereignCapabilities | None = None,
    ) -> None:
        self._service = SovereignService(store=store, capabilities=capabilities)

    def status(self) -> SovereignStatus:
        return self._service.get_status()

    def capabilities(self) -> SovereignCapabilities:
        return self._service.get_capabilities()

    async def blast_radius(
        self,
        ctx: SovereignContext,
        *,
        actor_identity_id: str,
        extra: frozenset[str] = frozenset(),
    ):
        return await self._service.simulate_blast_radius_async(
            ctx, actor_identity_id=actor_identity_id, hypothetical_extra_capabilities=extra
        )
