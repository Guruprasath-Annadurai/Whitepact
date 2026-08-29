"""Tests for Enterprise Neural Phase 5 —
`governance/neural/device.py`'s `DeviceTrustLevel`, `CapabilityState`,
`NeuralCapabilityManifest`, and `max_capability_state_for_trust_level`.
See `docs/enterprise-neural/05_PHASE5_DESIGN.md`.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.neural import (
    CapabilityState,
    DeviceTrustLevel,
    NeuralCapabilityManifest,
    max_capability_state_for_trust_level,
)


def _manifest(
    trust_level: DeviceTrustLevel = DeviceTrustLevel.TRUST_A,
    capabilities: dict[str, CapabilityState] | None = None,
    channel_count: int = 8,
    sampling_rate_hz: float = 250.0,
) -> NeuralCapabilityManifest:
    return NeuralCapabilityManifest(
        device_identity="dev1",
        adapter_version="0.1",
        manufacturer="Acme",
        model="X1",
        firmware_version="1.0",
        transport="usb",
        channel_count=channel_count,
        sampling_rate_hz=sampling_rate_hz,
        trust_level=trust_level,
        capabilities=capabilities if capabilities is not None else {},
    )


class TestMaxCapabilityStateForTrustLevel:
    def test_trust_d_excludes_validated(self) -> None:
        allowed = max_capability_state_for_trust_level(DeviceTrustLevel.TRUST_D)
        assert CapabilityState.VALIDATED not in allowed
        assert CapabilityState.EXPERIMENTAL in allowed
        assert CapabilityState.UNAVAILABLE in allowed

    @pytest.mark.parametrize(
        "trust_level",
        [DeviceTrustLevel.TRUST_A, DeviceTrustLevel.TRUST_B, DeviceTrustLevel.TRUST_C],
    )
    def test_higher_trust_levels_allow_all_states(self, trust_level: DeviceTrustLevel) -> None:
        assert max_capability_state_for_trust_level(trust_level) == frozenset(CapabilityState)


class TestNeuralCapabilityManifest:
    def test_valid_construction(self) -> None:
        m = _manifest(capabilities={"attention": CapabilityState.VALIDATED})
        assert m.is_validated("attention")

    def test_rejects_empty_device_identity(self) -> None:
        with pytest.raises(ValueError, match="device_identity"):
            NeuralCapabilityManifest(
                device_identity="",
                adapter_version="0.1",
                manufacturer="Acme",
                model="X1",
                firmware_version=None,
                transport="usb",
                channel_count=8,
                sampling_rate_hz=250.0,
                trust_level=DeviceTrustLevel.TRUST_A,
                capabilities={},
            )

    def test_rejects_zero_channel_count(self) -> None:
        with pytest.raises(ValueError, match="channel_count"):
            _manifest(channel_count=0)

    def test_rejects_negative_channel_count(self) -> None:
        with pytest.raises(ValueError, match="channel_count"):
            _manifest(channel_count=-1)

    def test_rejects_zero_sampling_rate(self) -> None:
        with pytest.raises(ValueError, match="sampling_rate_hz"):
            _manifest(sampling_rate_hz=0.0)

    def test_rejects_negative_sampling_rate(self) -> None:
        with pytest.raises(ValueError, match="sampling_rate_hz"):
            _manifest(sampling_rate_hz=-10.0)

    def test_trust_d_with_validated_capability_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="trust_d"):
            _manifest(
                trust_level=DeviceTrustLevel.TRUST_D,
                capabilities={"attention": CapabilityState.VALIDATED},
            )

    def test_trust_d_with_experimental_capability_is_allowed(self) -> None:
        m = _manifest(
            trust_level=DeviceTrustLevel.TRUST_D,
            capabilities={"attention": CapabilityState.EXPERIMENTAL},
        )
        assert m.capability_state("attention") is CapabilityState.EXPERIMENTAL

    def test_capability_state_for_missing_capability_is_unavailable(self) -> None:
        m = _manifest(capabilities={})
        assert m.capability_state("nonexistent") is CapabilityState.UNAVAILABLE
        assert not m.is_validated("nonexistent")

    def test_is_validated_false_for_experimental(self) -> None:
        m = _manifest(capabilities={"yes_no": CapabilityState.EXPERIMENTAL})
        assert not m.is_validated("yes_no")

    def test_is_validated_false_for_unavailable(self) -> None:
        m = _manifest(capabilities={"inner_speech": CapabilityState.UNAVAILABLE})
        assert not m.is_validated("inner_speech")


class TestProperties:
    @given(
        trust_level=st.sampled_from(
            [DeviceTrustLevel.TRUST_A, DeviceTrustLevel.TRUST_B, DeviceTrustLevel.TRUST_C]
        ),
        state=st.sampled_from(list(CapabilityState)),
    )
    def test_non_trust_d_accepts_any_capability_state(
        self, trust_level: DeviceTrustLevel, state: CapabilityState
    ) -> None:
        m = _manifest(trust_level=trust_level, capabilities={"cap": state})
        assert m.capability_state("cap") is state

    @given(state=st.sampled_from([CapabilityState.EXPERIMENTAL, CapabilityState.UNAVAILABLE]))
    def test_trust_d_accepts_non_validated_states(self, state: CapabilityState) -> None:
        m = _manifest(trust_level=DeviceTrustLevel.TRUST_D, capabilities={"cap": state})
        assert m.capability_state("cap") is state

    def test_trust_d_never_accepts_validated_regardless_of_other_capabilities(self) -> None:
        with pytest.raises(ValueError):
            _manifest(
                trust_level=DeviceTrustLevel.TRUST_D,
                capabilities={
                    "a": CapabilityState.EXPERIMENTAL,
                    "b": CapabilityState.VALIDATED,
                    "c": CapabilityState.UNAVAILABLE,
                },
            )
