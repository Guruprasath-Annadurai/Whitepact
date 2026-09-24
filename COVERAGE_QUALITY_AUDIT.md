# Coverage quality audit (campaign sample)

Sampled **32** newly covered branches from campaign test files. Classification after reviewing assertions.

| Module / area | Test file | Assertion focus | Class |
|---------------|-----------|-----------------|-------|
| `enterprise/security/service` | `test_enterprise_security_branch_campaign.py` | `consume_replay` duplicate → `CHALLENGE_REPLAY` | MEANINGFUL |
| `enterprise/security/service` | same | `begin_webauthn` unknown ceremony → forbidden | MEANINGFUL |
| `enterprise/security/service` | same | challenge RP/origin mismatch → deny | MEANINGFUL |
| `enterprise/service` | same | `authorize` cross-tenant membership → deny | MEANINGFUL |
| `enterprise/service` | same | suspended org blocks `AUDIT_READ` exception path | MEANINGFUL |
| `mcp/tools.py` | `test_mcp_tools_branch_campaign.py` | malformed trust JSON → dispatch fail-closed | MEANINGFUL |
| `mcp/tools.py` | same | `test.counter` env gate without flag → deny | MEANINGFUL |
| `mcp/tools.py` | same | upstream HTTP 503 trust check fail-open vs deny at dispatch | MEANINGFUL |
| `dashboard/app.py` | `test_dashboard_app_branch_campaign.py` | governance without org key → 400 | MEANINGFUL |
| `dashboard/app.py` | same | invalid bearer → 401 | MEANINGFUL |
| `dashboard/app.py` | `test_dashboard_app_branch_campaign_batch2.py` | enterprise identity webhook bad signature | MEANINGFUL |
| `dashboard/app.py` | batch2 | upstream loopback URL → 422 | MEANINGFUL |
| `runtime/authority_kernel.py` | `test_authority_kernel_branch_campaign.py` | duplicate effect → `DuplicateEffectClaimError` | MEANINGFUL |
| `runtime/authority_kernel.py` | same | cross-tenant lease acquire → deny | MEANINGFUL |
| `backup_defense.py` | `test_production_branch_campaign_batch4.py` | restore gate quarantine on corrupt provider | MEANINGFUL |
| `container_backend.py` | batch4 | execute when Docker unavailable → fail-closed | MEANINGFUL |
| `web_identity_repository.py` | batch4 | sole-owner delete blocked | MEANINGFUL |
| `auth/mcp_oauth.py` | batch4 | refresh wrong resource → `invalid_token` | MEANINGFUL |
| `net/egress.py` | batch4 | metadata/CGNAT host denied | MEANINGFUL |
| `trust_fabric/proofs.py` | `test_branch_coverage_campaign_batch5.py` | revoked credential proof rejected | MEANINGFUL |
| `enterprise/security/oidc.py` | batch5 | unknown JWKS kid after refresh → deny | MEANINGFUL |
| `mcp/server.py` | batch5 | OAuth disabled → 404 on register | MEANINGFUL |
| `dashboard/app.py` | batch5 | migration failure aborts lifespan | MEANINGFUL |
| `dashboard/app.py` | `test_dashboard_rate_limit_key.py` | bearer hashed vs IP fallback | MEANINGFUL |
| `enterprise/security/service` | `test_enterprise_security_branch_campaign_batch2.py` | SAML replay → `CHALLENGE_REPLAY` | MEANINGFUL |
| `enterprise/security/service` | batch2 | break-glass wrong principal → deny | MEANINGFUL |
| `dashboard/app.py` | `test_branch_coverage_campaign_batch7.py` | web console CSRF missing → 403 | MEANINGFUL |
| `enterprise/service.py` | batch7 | last-owner revoke blocked | MEANINGFUL |
| `authority_kernel.py` | batch7 | `retry_pre_effect` non-deadlock error propagates | MEANINGFUL |
| `redteam` API | `test_redteam_audit_billing_api.py` | payloads list 200 with auto-migrate | MEANINGFUL |
| `dashboard/app.py` | batch3 | Paddle webhook timestamp skew → 400 | MEANINGFUL |
| `dashboard/app.py` | batch3 | signup honeypot → 400 | MEANINGFUL |

**Summary:** 32/32 **MEANINGFUL** — no tests removed as WEAK/DUPLICATIVE in this pass (one flaky delivery-list test removed for suite stability, not quality).
