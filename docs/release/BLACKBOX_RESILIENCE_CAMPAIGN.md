# Black-box & resilience campaign (PREPARATION)

**Status:** `HARNESS_READY` — **not** `FINAL_CAMPAIGN_EXECUTED`

## Architecture (later)

```
external partner/client
        ↓ HTTPS (black-box)
staging / evaluation tenant
        ↓
WhitePact UpstreamMCPExecutor (PUBLIC_ONLY)
        ↓
controlled bridge
        ↓
Hronaut MCP / disposable target
```

Invariants preserved:

- `DestinationPolicy.PUBLIC_ONLY` — no localhost/private IP via production-style paths
- Tenant isolation, authority chain, approval rules unchanged

## Harness location

- `tests/release_blackbox/` — scenario catalog, UNKNOWN semantics, fault matrix stubs
- `tests/release_blackbox/hronaut_bridge.py` — configuration template (no credentials)

## Scenarios (15)

See `test_scenario_catalog.py` — each ID must be executed on the **combined V1 RC SHA**.

Where external effect is unavailable now: **`FINAL_EXTERNAL_VALIDATION_PENDING`**

## Effect proof (C4)

| Layer | Proves |
|-------|--------|
| WhitePact evidence | decision, authorization, dispatch attempt, correlation, outcome/reconciliation |
| External read-back | whether external system actually changed |

Do not treat internal evidence alone as external final state.

## Resilience matrix

Registered in `test_resilience_fault_matrix.py` — injection runs on combined RC with disposable infra.

## UNKNOWN

- UNKNOWN ≠ SUCCESS
- UNKNOWN ≠ blind-retry FAILURE
- See `test_unknown_semantics.py` + governance outcome tests on combined RC

## Final campaign

After **COMBINED WHITEPACT V1 RC** exists:

1. Run `pytest tests/release_blackbox -m release_blackbox_prep`
2. Execute live Hronaut black-box with scoped credentials
3. Record evidence — **no FINAL PASS from this branch alone**
