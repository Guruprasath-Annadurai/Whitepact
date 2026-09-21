# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from responsibleai.sovereign.protocol import (
    CapabilityAvailability,
    SovereignCapabilities,
    SovereignFeature,
)


def test_capability_negotiation_phase_a_features_available() -> None:
    caps = SovereignCapabilities.negotiate()
    by_name = {f.name: f.availability for f in caps.features}
    assert by_name[SovereignFeature.STATUS] == CapabilityAvailability.AVAILABLE
    assert by_name[SovereignFeature.XRAY] == CapabilityAvailability.AVAILABLE
    assert by_name[SovereignFeature.SIMULATE_MISSION] == CapabilityAvailability.AVAILABLE
    assert by_name[SovereignFeature.GAUNTLET] == CapabilityAvailability.EXPERIMENTAL


def test_require_unavailable_raises() -> None:
    caps = SovereignCapabilities.negotiate()
    try:
        caps.require(SovereignFeature.FLIGHT_RECORDER)
        raise AssertionError("expected SovereignCapabilityError")
    except Exception as exc:
        assert "UNAVAILABLE" in str(exc)
