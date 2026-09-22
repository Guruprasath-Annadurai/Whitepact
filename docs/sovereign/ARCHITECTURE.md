# WhitePact Sovereign — Architecture (V1)

## Doctrine

WhitePact Sovereign exposes WhitePact's power. It never becomes WhitePact's authority.

Humans remain sovereign. Sovereign interfaces (Web, IDE, CLI, SDK) are read/simulation
surfaces over the same canonical service layer (`responsibleai.sovereign.service.SovereignService`).

## Layering

```
WhitePact Core (governance, runtime authority kernel, evidence)
        │
Sovereign Service Layer (read / simulate / explain / trace)
        │
Sovereign Canonical Protocol (capabilities, versions)
        │
   CLI · SDK · Web · IDE
```

## Phase B — Understand (repository-backed)

- `SovereignCanonicalStore` wires canonical read repositories (`sources.py`)
- `build_repository_xray()` — delegation/policy/ceiling/evidence topology (`xray_builder.py`)
- `explain_from_evidence()` / `explain_from_identity()` (`debugger.py`)
- `build_trace_from_evidence()` with explicit MISSING stages (`trace_builder.py`)
- `load_effective_authority()`, manifest compare/drift (`effective.py`, `authority_engine.py`)
- `observe_authority()` — non-authoritative fingerprint (`observation.py`)

All Phase B service entrypoints are `@zero_effect_operation` and async when backed by the store.

## Phase A foundation

- Protocol versioning and capability negotiation (`protocol.py`)
- Authority graph model with mandatory edge provenance (`graph.py`)
- `whitepact.yaml` manifest schema — expected authority only (`manifest.py`)
- `SovereignExecutionEnvelope` — represents facts, does not create grants (`models.py`)
- Tenant isolation helpers (`tenant.py`)
- Centralized redaction (`redaction.py`)
- Zero-effect operation markers (`zero_effect.py`)

## Non-goals

- No authority minting, grant issuance, or policy bypass paths in Sovereign
- No conflation of UNKNOWN with success or automatic retry
- No duplicate authority databases; derive views from canonical stores in later phases
