# M5 preparation status

**Status:** `M5_PREPARATION_ONLY — WAITING_FOR_QUALIFIED_M4_BASE`

| Field | Value |
|-------|--------|
| Parallel prep branch | `cursor/whitepact-m5-m6-parallel-prep-f7a9` |
| Lineage anchor (read-only) | Frozen M4 `52d9b3c5497af24bb7d4a7147e33deaadc64296e` |
| Qualified M3 | `620399b7973f5ed058d45218610be228e72d3ed8` |
| Authoritative M5 RC | **Not frozen** — do not treat PR #137 as final |

## Allowed now

- Rebuild plan, regression/chaos matrices, M6 evidence docs, clean-install smoke tests, supply-chain evidence indexes, cloud **static** hardening.

## Forbidden until Antigravity M4 PASS

- Freezing final M5 exact-head SHA
- Rebasing integrated RC onto a **new** M4 candidate without formal PASS
- Merging to `main`, publishing packages, production deploy

## On M4 PASS

Follow `docs/ws6/M5_REBUILD_PLAN.md` § "Activation checklist".
