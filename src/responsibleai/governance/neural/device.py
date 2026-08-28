"""Phase 5 (Enterprise Neural directive) — the BCI device trust and
capability contract. See `docs/enterprise-neural/05_PHASE5_DESIGN.md`.

No concrete device adapter ships in this module — see the design doc
Sec 1 for why building one now (with no real device or vendor SDK to
validate against) would be exactly the kind of prototype capability
fabrication the master directive prohibits. `BCIDeviceAdapter` is the
`Protocol` a real, future adapter implements.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from responsibleai.governance.neural.types import NeuralPayload


class DeviceTrustLevel(StrEnum):
    """Per the master directive §6. Trust is independent of
    capability — see `NeuralCapabilityManifest`'s own docstring and
    `max_capability_state_for_trust_level` for the one place trust
    *does* constrain capability (the VALIDATED ceiling)."""

    TRUST_A = "trust_a"  # hardware-backed or strongly attested device
    TRUST_B = "trust_b"  # strong authenticated vendor transport/integration
    TRUST_C = "trust_c"  # trusted WhitePact adapter, weak hardware identity
    TRUST_D = "trust_d"  # legacy/unverified device or transport


class CapabilityState(StrEnum):
    """Per the master directive §32. A capability must be exactly one
    of these — no UI, API, or documentation may imply a fourth,
    unstated state (e.g. a capability silently treated as validated
    without ever being assigned that state explicitly)."""

    VALIDATED = "validated"
    EXPERIMENTAL = "experimental"
    UNAVAILABLE = "unavailable"


def max_capability_state_for_trust_level(
    trust_level: DeviceTrustLevel,
) -> frozenset[CapabilityState]:
    """The set of `CapabilityState`s a manifest may claim for a device
    at *trust_level*. `TRUST_D` (legacy/unverified transport) may never
    claim `VALIDATED` for any capability — an unverified transport
    gives no basis for the measured-confidence claim a VALIDATED label
    implies (design doc Sec 2, directive §5's "WhitePact's own measured
    capability evidence determines what WhitePact labels validated" —
    evidence requires a trustworthy transport to measure over).
    `TRUST_A`/`TRUST_B`/`TRUST_C` may claim any state; this ceiling
    only restricts the weakest tier.
    """
    if trust_level is DeviceTrustLevel.TRUST_D:
        return frozenset({CapabilityState.EXPERIMENTAL, CapabilityState.UNAVAILABLE})
    return frozenset(CapabilityState)


@dataclass(frozen=True)
class NeuralCapabilityManifest:
    """The typed contract every future concrete device adapter must
    produce. Per the master directive §5: "compatibility != capability,
    compatibility != trust" — `trust_level` and `capabilities` are
    independent fields with no derivation between them, except the one
    explicit ceiling `max_capability_state_for_trust_level` enforces
    (checked in `__post_init__`, so an invalid manifest cannot be
    constructed at all, not merely discouraged by convention).
    """

    device_identity: str
    adapter_version: str
    manufacturer: str
    model: str
    firmware_version: str | None
    transport: str
    channel_count: int
    sampling_rate_hz: float
    trust_level: DeviceTrustLevel
    capabilities: Mapping[str, CapabilityState]
    signal_quality_requirements: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
        if not self.device_identity:
            raise ValueError("NeuralCapabilityManifest.device_identity must be non-empty")
        if self.channel_count < 1:
            raise ValueError(
                f"NeuralCapabilityManifest.channel_count must be >= 1, got {self.channel_count}"
            )
        if self.sampling_rate_hz <= 0:
            raise ValueError(
                "NeuralCapabilityManifest.sampling_rate_hz must be > 0, "
                f"got {self.sampling_rate_hz}"
            )
        allowed = max_capability_state_for_trust_level(self.trust_level)
        for name, state in self.capabilities.items():
            if state not in allowed:
                raise ValueError(
                    f"Capability {name!r} claims state {state.value!r}, which "
                    f"{self.trust_level.value!r} devices are not permitted to claim "
                    f"(allowed: {sorted(s.value for s in allowed)})"
                )

    def capability_state(self, name: str) -> CapabilityState:
        """Fail-closed lookup: a capability not present in the manifest
        is UNAVAILABLE, never silently treated as anything else."""
        return self.capabilities.get(name, CapabilityState.UNAVAILABLE)

    def is_validated(self, name: str) -> bool:
        return self.capability_state(name) is CapabilityState.VALIDATED


class BCIDeviceAdapter(Protocol):
    """The contract a real, future device adapter implements. No
    concrete implementation exists yet — see module docstring."""

    def get_capability_manifest(self) -> NeuralCapabilityManifest: ...

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    def stream(self) -> AsyncIterator[NeuralPayload]: ...
