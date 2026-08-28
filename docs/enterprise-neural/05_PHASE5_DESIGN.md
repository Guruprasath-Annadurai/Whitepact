# Phase 5 — Universal BCI Device + Trust Layer: Design

STATUS: Design only. No runtime code changed by this document.

## 0. Ground truth

Zero BCI hardware integration code exists (re-confirmed). No
`brainflow`, `pylsl`, or vendor SDK dependency is currently declared in
`pyproject.toml`.

## 1. What Phase 5 actually builds, and what it deliberately does not

Per the master directive's dependency policy (rule 48: "before adding a
dependency, determine whether existing code can safely provide the
requirement... verify maintenance... avoid dependencies for trivial
functionality") and rule 63 ("no prototypes, no placeholders, no fake
security claims") — **this phase does not add a BrainFlow/LSL/vendor-SDK
dependency or write fake device I/O**, because there is no real device
to validate an integration against and no one asking for a specific
vendor. Doing so now would produce exactly the kind of prototype code
the directive prohibits: an adapter that "works" only against invented
test fixtures, never a real device, with capability claims nobody
verified.

What this phase *does* build, and is honest about the boundary:

1. **`NeuralCapabilityManifest`** — the typed contract every future
   concrete device adapter must produce, with `DeviceTrustLevel` and
   `CapabilityState` (VALIDATED/EXPERIMENTAL/UNAVAILABLE, per the
   directive's §32) enforced structurally.
2. **`DeviceTrustLevel`** classification (TRUST_A-D) and the invariant
   that trust and capability are independent axes — a manifest cannot
   claim a capability is VALIDATED without evidence, and low trust
   restricts which capabilities may be VALIDATED at all, enforced in
   code, not by convention.
3. **`BCIDeviceAdapter`** — a `Protocol` (interface only) that a real,
   future BrainFlow/LSL/vendor adapter would implement. Defining the
   contract now, without a fake implementation, is the honest version
   of "prepare for Phase 5's device integration" — a concrete adapter
   is future work gated on an actual device/vendor decision, not
   something to fabricate.

## 2. Device trust levels

```python
class DeviceTrustLevel(StrEnum):
    TRUST_A = "trust_a"  # hardware-backed or strongly attested
    TRUST_B = "trust_b"  # strong authenticated vendor transport/integration
    TRUST_C = "trust_c"  # trusted WhitePact adapter, weak hardware identity
    TRUST_D = "trust_d"  # legacy/unverified device or transport
```

**Trust never implies capability, and capability never implies trust** —
the directive's own "compatibility != capability != trust" (§5, §32).
Enforced by keeping `DeviceTrustLevel` and `CapabilityState` on
entirely separate fields with no derivation between them, plus an
explicit policy function (`max_capability_state_for_trust_level`) that
caps what a given trust level may ever claim as VALIDATED — e.g. a
`TRUST_D` device can still report EXPERIMENTAL or UNAVAILABLE
capabilities, but the policy function refuses to let a `TRUST_D`
manifest claim any capability as VALIDATED for the constitutional laws'
highest-risk category (this phase defines the mechanism; which specific
capabilities count as "highest risk" is a Phase 6/7 concern once real
capability names exist beyond the generic placeholders below).

## 3. Capability state

Reused from the directive's own §32, not reinvented:

```python
class CapabilityState(StrEnum):
    VALIDATED = "validated"
    EXPERIMENTAL = "experimental"
    UNAVAILABLE = "unavailable"
```

## 4. `NeuralCapabilityManifest`

```python
@dataclass(frozen=True)
class NeuralCapabilityManifest:
    device_identity: str
    adapter_version: str
    manufacturer: str
    model: str
    firmware_version: str | None
    transport: str
    channel_count: int
    sampling_rate_hz: float
    trust_level: DeviceTrustLevel
    capabilities: Mapping[str, CapabilityState]  # capability name -> state
    signal_quality_requirements: Mapping[str, float] | None = None
```

**Validated-capability evidence, not marketing claims** — the directive's
§5 explicitly: "Do not allow marketing capability labels to come
directly from manufacturer claims. WhitePact's own measured capability
evidence determines what WhitePact labels validated." Enforced by
`NeuralCapabilityManifest` never being constructed directly from raw
vendor metadata — a future concrete adapter's `BCIDeviceAdapter.probe()`
method is documented (interface-level) as required to run WhitePact's
own measurement before setting any capability to VALIDATED, not to copy
a vendor spec sheet. This phase can't enforce that at the type level
alone (there's no measurement code to call yet) — flagged as a Phase
6-era responsibility, not silently assumed handled.

## 5. `BCIDeviceAdapter` Protocol

```python
class BCIDeviceAdapter(Protocol):
    def get_capability_manifest(self) -> NeuralCapabilityManifest: ...
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def stream(self) -> AsyncIterator[NeuralPayload]: ...  # N0/N1, per Phase 4's types
```

No concrete implementation ships this phase. This is the seam a real
adapter (once a vendor/protocol decision is made) implements, mirroring
how `governance/crypto/provider.py`'s `KeyProvider` Protocol preceded
`LocalEnvelopeKeyProvider`'s concrete implementation in Phase 2 — except
here, unlike Phase 2, there genuinely is no "local, always-available"
concrete implementation to build alongside the Protocol, since every
real implementation requires actual hardware or a real SDK.

## 6. What Phase 5 does not do

- No BrainFlow/LSL/vendor SDK dependency added.
- No concrete adapter (would require a real device or SDK to validate
  against — building one now would be exactly the "prototype capability
  fabrication" the directive prohibits).
- No capability-measurement/probing logic (needs a real device signal
  to measure against — Phase 6's decoder-safety work is the natural
  place capability *measurement* logic would eventually live, once a
  device exists to measure).

## 7. Implementation plan

1. `governance/neural/device.py`: `DeviceTrustLevel`, `CapabilityState`,
   `NeuralCapabilityManifest`, `BCIDeviceAdapter` Protocol,
   `max_capability_state_for_trust_level` policy helper.
2. Tests: manifest construction/validation, trust-capability
   independence, the trust-level capability cap.
3. `docs/enterprise-neural/05_PHASE5_REPORT.md`.

Phase 5 design complete. Proceeding to implementation.
