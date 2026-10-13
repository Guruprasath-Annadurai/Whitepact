# WhitePact Production Launch Evidence (Cell B — final pass)

## Measured results (disposable PostgreSQL / local HTTP)

| Artifact | Measurement |
|----------|-------------|
| `b4-restore-rehearsal.json` | backup ~0.066s, restore ~0.4s, 118 public tables |
| `b4-restore-seed-rehearsal.json` | seeded org row restored after logical backup |
| `b9-http-pg-load.json` | burst ~283 RPS, soak ~305 RPS, 20s soak, p95 ~8–14 ms (single uvicorn + PG) |
| `b9-load-smoke.json` | TestClient only — not production capacity evidence |

## B9 operating limits (conservative, from local qualification)

- Single uvicorn worker on isolated PG: ~300 RPS health endpoint before errors (0 errors observed in qualification run).
- Soak 20s at ~300 RPS showed no error growth in qualification environment — **not** a 24h leak test.

## B10

- Bad production Helm values (auth disabled) blocked by `helm_validate`.
- Live `helm rollback` on a cluster: **OWNER_ACTION_REQUIRED** — see `B10_ROLLBACK_PROCEDURE.md`.

## B12

Run: `bash scripts/cell_b/b12_zero_to_launch_rehearsal.sh`  
Output: `artifacts/production/b12-zero-to-launch-summary.json` (SELF_REHEARSED).

## Independent validation

Stranger-operator and representative staging multi-replica qualification: **NOT_TESTED** in Cell B zero-cost VM.
