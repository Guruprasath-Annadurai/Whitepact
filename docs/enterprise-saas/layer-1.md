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

## Verified principal (Layer 1 remediation)

Reusable API credentials require `IDENTITY_VERIFIED` in **every**
environment (development, staging, production). `BASIC_VERIFIED` is
onboarding-only and never sufficient for `wp_test_*` / `wp_staging_*` /
`wp_live_*` keys.

Hosted issuance is `EnterpriseIAM.create_api_key` /
`issue_api_key`, gated by `CredentialIssuancePolicy`.
`OrgRepository.create_key` is an internal fixture/migration insert.

Production startup fails closed if `RAI_API_KEYS` is set or if
`WHITEPACT_IDENTITY_WEBHOOK_SECRET` is missing, empty, a known
development default, or trivially weak.

Production remains disabled: `PRODUCTION_GATE_B_OPEN=False`,
`PHASE7A_DISPATCHER_ENABLED` defaults false.

## Console backend routes

Mounted at `/api/enterprise/*` and `/api/v1/enterprise/*` (version rewrite).

See `src/responsibleai/enterprise/router.py`.
