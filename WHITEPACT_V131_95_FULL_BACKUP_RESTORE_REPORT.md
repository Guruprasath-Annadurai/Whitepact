# Full backup / restore (Phase 0B)

**Verdict:** **PASS** (destroy + restore + manifest match)

**Population depth:** **PASS** (multi-org users, keys, policies, evidence chain, approvals, nonces, audit, paddle webhook, webhook config)

Dump size: 306480 bytes

## Checks

```json
{
  "table_counts": true,
  "alembic": true,
  "integrity_sample": true,
  "tenant_isolation": true,
  "app_boot": true
}
```

## Post-restore app boot

```json
{
  "port": 40143,
  "pid": 648423,
  "health_status": 200,
  "health_body": "{\"status\":\"healthy\",\"version\":\"1.3.1\",\"uptime_seconds\":2.1,\"timestamp\":\"2026-09-25T08:01:36.981601+00:00\",\"checks\":{\"database\":\"ok\",\"db_backend\":\"postgresql\",\"rate_limit_backend\":\"memory\",\"otel\":\"disabled\",\"auth\":\"disabled\",\"websocket_connections\":0,\"webhooks_registered\":1,\"orgs\":2},\"modules\":[\"trust_score\",\"ai_passport\",\"guardrails\",\"hallucination\",\"compliance\",\"redteam\",\"cost_tracker\",\"cost_analyzer\",\"model_router\",\"drift_monitor\",\"websockets\",\"webhooks\",\"prometheus\",\"rbac\",\"orgs\",\"audit_log\",",
  "ok": true
}
```

## Pre manifest

```json
{
  "orgs": [
    "tenant_alpha",
    "tenant_beta"
  ],
  "users": [
    "usr_alpha_admin",
    "usr_alpha_viewer",
    "usr_beta_member"
  ],
  "api_keys": {
    "active": [
      "key_alpha_act",
      "key_beta_act"
    ],
    "revoked": [
      "key_alpha_rev"
    ]
  },
  "evidence_ids": [
    "ev_alpha_1",
    "ev_alpha_2",
    "ev_beta_1"
  ],
  "chain_heads": {
    "tenant_alpha": "hash_head_alpha",
    "tenant_beta": "hash_head_beta"
  },
  "approvals": {
    "pending": [
      "app_alpha_pnd"
    ],
    "approved": [
      "app_beta_done"
    ],
    "rejected": [
      "app_beta_rej"
    ]
  },
  "nonces": [
    "nonce_alpha_1"
  ],
  "paddle_events": [
    "evt_paddle_1"
  ],
  "table_counts": {
    "organizations": 2,
    "web_users": 3,
    "web_memberships": 3,
    "org_api_keys": 3,
    "governance_evidence": 3,
    "governance_evidence_chain_heads": 2,
    "governance_policies": 2,
    "governance_approvals": 3,
    "governance_execution_nonces": 1,
    "governance_revocation_epochs": 2,
    "audit_log": 2,
    "paddle_webhook_events": 1,
    "webhook_configs": 1
  },
  "alembic_version": "0061"
}
```

## Post manifest

```json
{
  "table_counts": {
    "organizations": 2,
    "web_users": 3,
    "web_memberships": 3,
    "org_api_keys": 3,
    "governance_evidence": 3,
    "governance_evidence_chain_heads": 2,
    "governance_policies": 2,
    "governance_approvals": 3,
    "governance_execution_nonces": 1,
    "governance_revocation_epochs": 2,
    "audit_log": 2,
    "paddle_webhook_events": 1,
    "webhook_configs": 1
  },
  "alembic_version": "0061",
  "revoked_keys": [
    "key_alpha_rev"
  ],
  "alpha_chain_head": "hash_head_alpha",
  "cross_tenant_key_leak": 0
}
```
