# Enterprise SaaS Layer 1

Administrative identity and access control for WhitePact. This layer does
**not** grant execution authority. OWNER cannot skip Constitution → … →
Isolated Execution.

Canonical tenant remains `organizations`. Individual customers use
`workspace_kind=INDIVIDUAL` rather than fabricating a company.

## Run

```bash
PYTHONPATH=src pytest tests/ -ra
```

Production remains disabled: `PRODUCTION_GATE_B_OPEN=False`,
`PHASE7A_DISPATCHER_ENABLED` defaults false.

## Console backend routes

Mounted at `/api/enterprise/*` and `/api/v1/enterprise/*` (version rewrite).

See `src/responsibleai/enterprise/router.py`.
