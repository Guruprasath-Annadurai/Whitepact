# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical Sovereign protocol and capability negotiation.

Sovereign exposes governance truth; it never mints authority.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

SOVEREIGN_VERSION = "1.0.0"
PROTOCOL_VERSION = "1.0.0"


class CapabilityAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNSUPPORTED = "UNSUPPORTED"
    EXPERIMENTAL = "EXPERIMENTAL"


class SovereignFeature(StrEnum):
    STATUS = "status"
    XRAY = "xray"
    EXPLAIN = "explain"
    TRACE = "trace"
    AUTHORITY_EXPECTED = "authority_expected"
    AUTHORITY_EFFECTIVE = "authority_effective"
    AUTHORITY_DRIFT = "authority_drift"
    AUTHORITY_COMPARE = "authority_compare"
    SIMULATE_BLAST_RADIUS = "simulate_blast_radius"
    SIMULATE_MISSION = "simulate_mission"
    SHADOW = "shadow"
    POLICY_LAB = "policy_lab"
    GAUNTLET = "gauntlet"
    FLIGHT_RECORDER = "flight_recorder"
    TIME_MACHINE = "time_machine"
    EVIDENCE = "evidence"
    CAPSULE = "capsule"
    AUTHORITY_BOM = "authority_bom"


# Phase A: foundation features only; others reported honestly as UNAVAILABLE.
_PHASE_A_AVAILABLE = frozenset(
    {
        SovereignFeature.STATUS,
        SovereignFeature.XRAY,
        SovereignFeature.EXPLAIN,
        SovereignFeature.TRACE,
        SovereignFeature.AUTHORITY_EXPECTED,
        SovereignFeature.AUTHORITY_EFFECTIVE,
        SovereignFeature.AUTHORITY_COMPARE,
        SovereignFeature.AUTHORITY_DRIFT,
    }
)

_READ_ONLY = frozenset(_PHASE_A_AVAILABLE)
_SIMULATION = frozenset(
    {
        SovereignFeature.SIMULATE_BLAST_RADIUS,
        SovereignFeature.SIMULATE_MISSION,
        SovereignFeature.SHADOW,
        SovereignFeature.POLICY_LAB,
    }
)
_EVIDENCE = frozenset(
    {
        SovereignFeature.EVIDENCE,
        SovereignFeature.FLIGHT_RECORDER,
        SovereignFeature.TIME_MACHINE,
        SovereignFeature.CAPSULE,
    }
)


class FeatureDescriptor(BaseModel):
    name: SovereignFeature
    availability: CapabilityAvailability
    version: str | None = None
    read_only: bool = False
    simulation: bool = False
    notes: str | None = None


class SovereignCapabilities(BaseModel):
    sovereign_version: str = SOVEREIGN_VERSION
    protocol_version: str = PROTOCOL_VERSION
    features: list[FeatureDescriptor] = Field(default_factory=list)

    @classmethod
    def negotiate(cls) -> SovereignCapabilities:
        features: list[FeatureDescriptor] = []
        for feat in SovereignFeature:
            if feat in _PHASE_A_AVAILABLE:
                avail = CapabilityAvailability.AVAILABLE
            elif feat in (SovereignFeature.GAUNTLET, SovereignFeature.AUTHORITY_BOM):
                avail = CapabilityAvailability.EXPERIMENTAL
            else:
                avail = CapabilityAvailability.UNAVAILABLE
            features.append(
                FeatureDescriptor(
                    name=feat,
                    availability=avail,
                    version="1.0.0" if avail == CapabilityAvailability.AVAILABLE else None,
                    read_only=feat in _READ_ONLY,
                    simulation=feat in _SIMULATION,
                    notes=None
                    if avail == CapabilityAvailability.AVAILABLE
                    else "Not implemented in this build phase",
                )
            )
        return cls(features=features)

    def require(self, feature: SovereignFeature) -> None:
        from responsibleai.sovereign.errors import SovereignCapabilityError

        for desc in self.features:
            if desc.name != feature:
                continue
            if desc.availability in (
                CapabilityAvailability.AVAILABLE,
                CapabilityAvailability.EXPERIMENTAL,
            ):
                return
            raise SovereignCapabilityError(f"Feature {feature.value} is {desc.availability.value}")
        raise SovereignCapabilityError(f"Feature {feature.value} is unknown")


class SovereignStatus(BaseModel):
    sovereign_version: str
    protocol_version: str
    doctrine: str = (
        "WhitePact Sovereign exposes WhitePact's power; it never becomes WhitePact's authority."
    )
    capabilities: SovereignCapabilities
    metadata: dict[str, Any] = Field(default_factory=dict)
