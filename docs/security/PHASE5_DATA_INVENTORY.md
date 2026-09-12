<!--
Copyright (c) 2026 Guruprasath Annadurai
SPDX-License-Identifier: MIT
-->

# WhitePact Phase 5: Authoritative Data Inventory & Classification Matrix

**Document:** `docs/security/PHASE5_DATA_INVENTORY.md`  
**Target Branch:** `feature/policy-data-governance-phase5`  

---

## 1. Table Classification Matrix (51+ Tables)

| # | Table Name | Data Classification | Sensitivity Tier | Retention Model | Deletion / Erasure Action |
|---|------------|---------------------|------------------|-----------------|---------------------------|
| 1 | `organizations` | SYSTEM_METADATA | HIGH | PERMANENT | Tombstoned / Generational update |
| 2 | `web_users` | PERSONAL | HIGH | ACCOUNT_LIFETIME | Pseudonymized / Soft-anonymized |
| 3 | `web_identities` | PERSONAL | HIGH | ACCOUNT_LIFETIME | Deleted on tenant erasure |
| 4 | `web_sessions` | PERSONAL | CRITICAL | SESSION_EXPIRY | Hard deleted immediately |
| 5 | `web_memberships` | TENANT_OPERATIONAL | MEDIUM | MEMBERSHIP_LIFETIME | Hard deleted on tenant erasure |
| 6 | `web_verification_tokens` | PERSONAL | HIGH | 24H_TTL | Hard deleted on expiry/erasure |
| 7 | `org_api_keys` | SENSITIVE_SECURITY | CRITICAL | KEY_LIFETIME | Revoked & Deleted on erasure |
| 8 | `incidents` | TENANT_OPERATIONAL | MEDIUM | 90D_DEFAULT | Hard deleted on erasure |
| 9 | `public_incident_reports` | PUBLIC | LOW | INDEFINITE | Anonymized / Retained public |
| 10 | `governance_evidence` | CANONICAL_SECURITY_EVIDENCE | CRITICAL | SECURITY_EVIDENCE_DEFAULT | Sealed / FK RESTRICT |
| 11 | `governance_evidence_chain_heads` | CANONICAL_SECURITY_EVIDENCE | CRITICAL | SECURITY_EVIDENCE_DEFAULT | Sealed / FK RESTRICT |
| 12 | `governance_approvals` | TENANT_OPERATIONAL | HIGH | 1YR_RETENTION | Hard deleted on erasure |
| 13 | `governance_approval_votes` | TENANT_OPERATIONAL | MEDIUM | 1YR_RETENTION | Hard deleted on erasure |
| 14 | `governance_policies` | TENANT_OPERATIONAL | HIGH | ACTIVE_LIFETIME | Deprecated / Replaced by 5A |
| 15 | `governance_policy_versions` | TENANT_OPERATIONAL | HIGH | ACTIVE_LIFETIME | Deprecated / Replaced by 5A |
| 16 | `governance_policy_revisions` | CANONICAL_SECURITY_EVIDENCE | HIGH | SECURITY_EVIDENCE_DEFAULT | Sealed / Immutably retained |
| 17 | `governance_policy_activations` | CANONICAL_SECURITY_EVIDENCE | HIGH | SECURITY_EVIDENCE_DEFAULT | Sealed / Immutably retained |
| 18 | `upstream_mcp_servers` | TENANT_OPERATIONAL | MEDIUM | ACTIVE_LIFETIME | Hard deleted on erasure |
| 19 | `org_authority_ceilings` | TENANT_OPERATIONAL | HIGH | ACTIVE_LIFETIME | Hard deleted on erasure |
| 20 | `governance_workflow_rules` | TENANT_OPERATIONAL | MEDIUM | ACTIVE_LIFETIME | Hard deleted on erasure |
| 21 | `governance_delegations` | TENANT_OPERATIONAL | HIGH | ACTIVE_LIFETIME | Revoked & Hard deleted |
| 22 | `org_autonomy_budgets` | TENANT_OPERATIONAL | MEDIUM | ACTIVE_LIFETIME | Hard deleted on erasure |
| 23 | `tool_trust_scores` | TENANT_OPERATIONAL | LOW | 30D_TTL | Hard deleted on erasure |
| 24 | `credential_issuances` | SENSITIVE_SECURITY | HIGH | TOKEN_LIFETIME | Revoked & Hard deleted |
| 25 | `governance_outcomes` | TENANT_OPERATIONAL | MEDIUM | 90D_DEFAULT | Hard deleted on erasure |
| 26 | `verified_principals` | TENANT_OPERATIONAL | HIGH | ACTIVE_LIFETIME | Revoked & Hard deleted |
| 27 | `intent_contracts` | TENANT_OPERATIONAL | HIGH | ACTIVE_LIFETIME | Hard deleted on erasure |
| 28 | `authority_passports` | TENANT_OPERATIONAL | HIGH | PASSPORT_LIFETIME | Revoked & Hard deleted |
| 29 | `trust_passports` | TENANT_OPERATIONAL | HIGH | PASSPORT_LIFETIME | Revoked & Hard deleted |
| 30 | `mcp_oauth_credentials` | SENSITIVE_SECURITY | CRITICAL | ACTIVE_LIFETIME | Revoked & Hard deleted |
| 31 | `mcp_oauth_codes` | SENSITIVE_SECURITY | CRITICAL | 10M_TTL | Hard deleted |
| 32 | `mcp_oauth_tokens` | SENSITIVE_SECURITY | CRITICAL | TOKEN_LIFETIME | Revoked & Hard deleted |
| 33 | `mcp_auth_events` | TENANT_OPERATIONAL | MEDIUM | 90D_DEFAULT | Hard deleted on erasure |
| 34 | `crypto_keys` | CREDENTIAL_SECRET | CRITICAL | KEY_LIFETIME | Zeroed / Hard deleted |
| 35 | `neural_vault_indices` | TENANT_OPERATIONAL | MEDIUM | ACTIVE_LIFETIME | Hard deleted on erasure |
| 36 | `neural_consent_records` | CANONICAL_SECURITY_EVIDENCE | HIGH | SECURITY_EVIDENCE_DEFAULT | Sealed / FK RESTRICT |
| 37 | `governance_root_authority_records` | CANONICAL_SECURITY_EVIDENCE | CRITICAL | SECURITY_EVIDENCE_DEFAULT | Sealed / FK RESTRICT |
| 38 | `governance_consent_proofs` | CANONICAL_SECURITY_EVIDENCE | CRITICAL | SECURITY_EVIDENCE_DEFAULT | Sealed / FK RESTRICT |
| 39 | `governance_revocation_epochs` | TENANT_OPERATIONAL | HIGH | ACTIVE_LIFETIME | Invalidated & Reset |
| 40 | `governance_execution_nonces` | SENSITIVE_SECURITY | HIGH | 1H_TTL | Hard deleted |
| 41 | `eval_runs` | TENANT_OPERATIONAL | LOW | 30D_TTL | Hard deleted on erasure |
| 42 | `eval_baselines` | TENANT_OPERATIONAL | LOW | 90D_TTL | Hard deleted on erasure |
| 43 | `mcp_tool_calls` | TENANT_OPERATIONAL | MEDIUM | 30D_TTL | Hard deleted on erasure |
| 44 | `token_usage` | TENANT_OPERATIONAL | LOW | 90D_TTL | Hard deleted on erasure |
| 45 | `cost_attribution` | TENANT_OPERATIONAL | LOW | 90D_TTL | Hard deleted on erasure |
| 46 | `audit_log` | CANONICAL_SECURITY_EVIDENCE | HIGH | SECURITY_EVIDENCE_DEFAULT | Sealed / Immutably retained |
| 47 | `stripe_webhook_events` | TENANT_OPERATIONAL | MEDIUM | 30D_TTL | Hard deleted / Set Null |
| 48 | `leaderboard_providers` | PUBLIC | LOW | INDEFINITE | Retained public |
| 49 | `leaderboard_evaluations` | PUBLIC | LOW | INDEFINITE | Retained public |
| 50 | `leaderboard_submissions` | PUBLIC | LOW | INDEFINITE | Retained public |
| 51 | `leaderboard_metrics` | PUBLIC | LOW | INDEFINITE | Retained public |
| 52 | `iam_sessions` | PERSONAL | CRITICAL | SESSION_EXPIRY | Hard deleted immediately |
| 53 | `iam_api_key_lineage` | SENSITIVE_SECURITY | CRITICAL | KEY_LIFETIME | Revoked & Hard deleted |
| 54 | `iam_scim_users` | PERSONAL | HIGH | ACCOUNT_LIFETIME | Hard deleted on erasure |
| 55 | `iam_scim_groups` | TENANT_OPERATIONAL | MEDIUM | ACTIVE_LIFETIME | Hard deleted on erasure |
| 56 | `iam_jit_grants` | SENSITIVE_SECURITY | HIGH | GRANT_LIFETIME | Revoked & Hard deleted |
| 57 | `iam_four_eyes_requests` | TENANT_OPERATIONAL | HIGH | 1YR_RETENTION | Hard deleted on erasure |
| 58 | `iam_break_glass_sessions` | SENSITIVE_SECURITY | CRITICAL | 24H_TTL | Revoked & Hard deleted |
| 59 | `iam_recovery_policies` | SENSITIVE_SECURITY | CRITICAL | ACTIVE_LIFETIME | Revoked & Hard deleted |
| 60 | `iam_recovery_challenges` | SENSITIVE_SECURITY | CRITICAL | 24H_TTL | Revoked & Hard deleted |
| 61 | `iam_privileged_audit_log` | CANONICAL_SECURITY_EVIDENCE | CRITICAL | SECURITY_EVIDENCE_DEFAULT | Sealed / Immutably retained |
| 62 | `iam_step_up_nonces` | SENSITIVE_SECURITY | CRITICAL | 15M_TTL | Hard deleted |
| 63 | `data_retention_policies` | TENANT_OPERATIONAL | HIGH | ACTIVE_LIFETIME | Hard deleted on erasure |
| 64 | `data_lifecycle_requests` | CANONICAL_SECURITY_EVIDENCE | HIGH | SECURITY_EVIDENCE_DEFAULT | Sealed / Immutably retained |
| 65 | `data_holds` | CANONICAL_SECURITY_EVIDENCE | HIGH | SECURITY_EVIDENCE_DEFAULT | Sealed / Immutably retained |
| 66 | `tenant_tombstones` | CANONICAL_SECURITY_EVIDENCE | CRITICAL | PERMANENT | Permanent ledger row |
| 67 | `restore_reconciliation_records` | CANONICAL_SECURITY_EVIDENCE | CRITICAL | SECURITY_EVIDENCE_DEFAULT | Sealed / Immutably retained |

---

## 2. In-Memory & Ephemeral Caches

- **Rate Limiting Sliding Windows**: Evicted immediately on tenant quarantine or erasure.
- **Memory Firewall & Context Store**: Cleared on tenant erasure.
- **Upstream Connection Cache**: Terminated on tenant erasure.
