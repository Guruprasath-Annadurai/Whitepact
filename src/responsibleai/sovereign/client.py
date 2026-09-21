# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Python SDK for Sovereign."""

from __future__ import annotations

from enum import StrEnum

from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.protocol import SovereignCapabilities, SovereignStatus
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.sources import SovereignCanonicalStore


class RetryClass(StrEnum):
    SAFE_TO_RETRY = "SAFE_TO_RETRY"
    CONDITIONALLY_RETRYABLE = "CONDITIONALLY_RETRYABLE"
    NEVER_BLINDLY_RETRY = "NEVER_BLINDLY_RETRY"


RETRY_MAP: dict[str, RetryClass] = {
    "status": RetryClass.SAFE_TO_RETRY,
    "capabilities": RetryClass.SAFE_TO_RETRY,
    "xray": RetryClass.SAFE_TO_RETRY,
    "explain": RetryClass.SAFE_TO_RETRY,
    "trace": RetryClass.SAFE_TO_RETRY,
    "effective": RetryClass.SAFE_TO_RETRY,
    "drift": RetryClass.SAFE_TO_RETRY,
    "compare": RetryClass.SAFE_TO_RETRY,
    "simulate_blast_radius": RetryClass.NEVER_BLINDLY_RETRY,
    "simulate_mission": RetryClass.NEVER_BLINDLY_RETRY,
    "shadow": RetryClass.NEVER_BLINDLY_RETRY,
    "gauntlet": RetryClass.NEVER_BLINDLY_RETRY,
    "capsule_reproduce": RetryClass.NEVER_BLINDLY_RETRY,
    "grant": RetryClass.NEVER_BLINDLY_RETRY,
    "execute": RetryClass.NEVER_BLINDLY_RETRY,
}


class SovereignClient:
    def __init__(
        self,
        store: SovereignCanonicalStore | None = None,
        capabilities: SovereignCapabilities | None = None,
    ) -> None:
        self._service = SovereignService(store=store, capabilities=capabilities)

    @property
    def service(self) -> SovereignService:
        return self._service

    def status(self) -> SovereignStatus:
        return self._service.get_status()

    def capabilities(self) -> SovereignCapabilities:
        return self._service.get_capabilities()

    def retry_class(self, operation: str) -> RetryClass:
        return RETRY_MAP.get(operation, RetryClass.CONDITIONALLY_RETRYABLE)

    async def xray(self, ctx: SovereignContext):
        return await self._service.build_xray_async(ctx)

    async def explain_evidence(self, ctx: SovereignContext, evidence_id: str):
        return await self._service.explain_evidence_async(ctx, evidence_id)

    async def trace(self, ctx: SovereignContext, evidence_id: str):
        return await self._service.trace_evidence_async(ctx, evidence_id)

    async def effective(self, ctx: SovereignContext):
        return await self._service.load_effective_async(ctx)

    async def blast_radius(
        self, ctx: SovereignContext, *, actor: str, extra: frozenset[str] = frozenset()
    ):
        return await self._service.simulate_blast_radius_async(
            ctx, actor_identity_id=actor, hypothetical_extra_capabilities=extra
        )

    async def mission(self, ctx: SovereignContext, *, agent_id: str, steps: list[str]):
        return await self._service.simulate_mission_async(ctx, agent_id=agent_id, steps=steps)

    async def gauntlet(self, ctx: SovereignContext, *, probe_ids: list[str] | None = None):
        return await self._service.run_gauntlet_async(ctx, probe_ids=probe_ids)

    async def correlate(self, ctx: SovereignContext, evidence_id: str):
        return await self._service.correlate_evidence_async(ctx, evidence_id)

    async def compare(self, ctx: SovereignContext, manifest):
        return await self._service.compare_manifest_async(ctx, manifest)

    async def drift(self, ctx: SovereignContext, manifest):
        return await self._service.detect_drift_async(ctx, manifest)

    async def shadow(
        self,
        ctx: SovereignContext,
        *,
        agent_id: str,
        action_type: str,
        target: str = "shadow:target",
    ):
        return self._service.evaluate_shadow(
            ctx, agent_id=agent_id, action_type=action_type, target=target
        )

    def lint_policy(self, rules):
        return self._service.lint_policy_rules(rules)

    async def policy_test(self, ctx: SovereignContext, cases):
        return await self._service.run_policy_tests_async(ctx, cases)

    async def policy_diff(self, ctx: SovereignContext, rules):
        return await self._service.diff_policy_async(ctx, rules)

    async def policy_simulate(self, ctx: SovereignContext, *, rules, action_types: list[str]):
        return await self._service.simulate_policy_async(
            ctx, candidate_rules=rules, action_types=action_types
        )

    async def flight_recorder(self, ctx: SovereignContext, evidence_id: str):
        return await self._service.flight_recorder_async(ctx, evidence_id)

    async def time_machine(self, ctx: SovereignContext, then_snapshot=None):
        return await self._service.time_machine_async(ctx, then_snapshot=then_snapshot)

    def create_capsule(self, ctx: SovereignContext, **kwargs):
        return self._service.create_capsule(ctx, **kwargs)

    def validate_capsule(self, capsule):
        return self._service.validate_capsule(capsule)

    def reproduce_capsule(self, capsule):
        return self._service.reproduce_capsule(capsule)

    async def authority_bom(self, ctx: SovereignContext):
        return await self._service.authority_bom_async(ctx)
