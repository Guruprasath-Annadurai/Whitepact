# Live distributed race (Phase 0B)

**Verdict:** **PASS** — 4 uvicorn workers, shared PostgreSQL, barrier bursts on `/api/health`.

```json
{
  "workers": 4,
  "barrier_health": [
    {
      "path": "/api/health",
      "n": 32,
      "codes": [
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200
      ],
      "all_200": true
    },
    {
      "path": "/api/health",
      "n": 32,
      "codes": [
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200
      ],
      "all_200": true
    }
  ],
  "continuous": {
    "samples": 803,
    "errors": 0
  }
}
```

Note: approval/nonce/API-key races remain covered by `tests/test_concurrency.py` and enterprise race pytest subsets; this harness proves live multi-process serving.


Pytest race/concurrency subset: **PASS**
