# WhitePact Phase 7A: Authority Mutation & Revocation Epoch Coverage Matrix

**Document Status:** CANONICAL SPECIFICATION PASS 4.4 (FINAL SPECIFICATION CLOSURE)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`

**Canonical migration ownership:** `docs/phase7a-execution/migration-ownership.md` (implemented `0049` = org governance lifecycle).

---

## 1. Problem Statement: Time-of-Check to Time-of-Use (TOCTOU)

In an asynchronous execution engine, an authorization is issued at `T0`, enqueued in a multi-tenant queue, and dequeued by a worker at `T1` (which may be seconds or minutes later).
If an administrator revokes a policy, suspends an organization's governance lifecycle, terminates an emergency BreakGlass session, or revokes a principal/key between `T0` and `T1`, the queued authorization MUST NOT be admitted or executed.

Canonical WhitePact provides a centralized epoch mechanism: `governance_revocation_epochs` and `lock_epoch(conn, organization_id, scope="governance")`.
When canonical `admit_execution()` runs under row lock, it asserts that `expected_epoch == current_epoch`. If the epoch was incremented, admission fails closed immediately with `StaleRevocationEpochError`.

The independent security audit demonstrated that the previous citation of "14 authority mutations" was a nominal early estimate. The actual repository contains an **audited inventory of 26 distinct production authority mutations across 13 domain subsystems**. This document inventories every single production mutation and proves universal epoch advancement.

---

## 2. Audited Production Authority Mutation Inventory (26 Mutations across 13 Subsystems)

| # | Subsystem | Mutation Operation | Repository / Service Method | Source File & Line | Security Meaning | Scope Bumped | Same TX? | Proving Test |
|---|---|---|---|---|---|---|---|---|
| 1 | **Organization** | Deletion | `OrgRepository.delete_org()` | `db/org_repository.py:462` | Organization permanently deleted; invalidates all pending authorizations. | `governance` | YES | `test_governance_persistence.py` |
| 2 | **Organization** | API Key Revocation | `OrgRepository.revoke_key()` | `db/org_repository.py:439` | API key revoked; invalidates outstanding permits issued under key. | `governance` | YES | `test_governance_persistence.py` |
| 3 | **Organization** | Governance Suspension | `OrgRepository.set_governance_status()` | `db/org_repository.py` | Organization suspended administratively (`organizations.governance_status`). | `governance` | YES | `test_governance_persistence.py` |
| 4 | **Authority Ceiling** | Update Ceiling | `OrgAuthorityCeilingRepository.set_ceiling()` | `db/org_authority_ceiling_repository.py:86` | Permissible authority ceiling lowered/changed; invalidates queued permits. | `governance` | YES | `test_org_authority_ceiling.py` |
| 5 | **Authority Ceiling** | Reset Ceiling | `OrgAuthorityCeilingRepository.reset_ceiling()` | `db/org_authority_ceiling_repository.py:110` | Ceiling reset to default; invalidates queued permits. | `governance` | YES | `test_org_authority_ceiling.py` |
| 6 | **Autonomy Budget** | Update Budget | `OrgAutonomyBudgetRepository.set_budget()` | `db/org_autonomy_budget_repository.py:63` | Autonomy budget adjusted; invalidates queued autonomous actions. | `governance` | YES | `test_autonomy_budget.py` |
| 7 | **Autonomy Budget** | Reset Budget | `OrgAutonomyBudgetRepository.reset_budget()` | `db/org_autonomy_budget_repository.py:82` | Autonomy budget reset; invalidates queued autonomous actions. | `governance` | YES | `test_autonomy_budget.py` |
| 8 | **Policy Lifecycle** | Upsert Policy | `PolicyRepository.upsert_policy()` | `db/policy_repository.py:60` | Policy rule created/modified; invalidates permits under old rules. | `governance` | YES | `test_governance_policy.py` |
| 9 | **Policy Lifecycle** | Archive Policy | `PolicyLifecycleService.archive_policy()` | `governance/policy_lifecycle.py:358` | Policy archived/deactivated; invalidates policy-derived permits. | `governance` | YES | `test_governance_policy.py` |
| 10 | **Consent Proofs** | Record Consent | `ConsentProofRepository.record()` | `db/consent_proof_repository.py:64` | Consent proof created; updates explicit consent boundary. | `governance` | YES | `test_governance_persistence.py` |
| 11 | **Consent Proofs** | Revoke Consent | `ConsentProofRepository.revoke()` | `db/consent_proof_repository.py:141` | Consent withdrawn; immediately revokes consent-based permits. | `governance` | YES | `test_governance_persistence.py` |
| 12 | **Delegation** | Record Delegation | `DelegationRepository.record()` | `db/delegation_repository.py:126` | Delegation recorded; alters active delegation authority chain. | `governance` | YES | `test_delegation_chains.py` |
| 13 | **Delegation** | Revoke Delegation | `DelegationRepository.revoke()` | `db/delegation_repository.py:287` | Delegation revoked; invalidates outstanding delegated permits. | `governance` | YES | `test_delegation_chains.py` |
| 14 | **Root Authority** | Record Trust Root | `RootAuthorityRepository.record()` | `db/root_authority_repository.py:61` | Root trust anchor registered; alters root authority topology. | `governance` | YES | `test_governance_persistence.py` |
| 15 | **Root Authority** | Revoke Trust Root | `RootAuthorityRepository.revoke()` | `db/root_authority_repository.py:127` | Root trust anchor revoked; invalidates permits under that root. | `governance` | YES | `test_governance_persistence.py` |
| 16 | **Tool Trust** | Record Score | `ToolTrustRepository.record_score()` | `db/tool_trust_repository.py:99` | Tool score updated/degraded; invalidates queued permits for tool. | `governance` | YES | `test_tool_trust.py` |
| 17 | **Upstream Server** | Register Server | `UpstreamServerRepository.register()` | `db/upstream_repository.py:73` | Upstream server registered. | `governance` | YES | `test_upstream_gateway.py` |
| 18 | **Upstream Server** | Update URL | `UpstreamServerRepository.update_url()` | `db/upstream_repository.py:116` | Upstream URL modified; invalidates pending dispatches to old URL. | `governance` | YES | `test_upstream_gateway.py` |
| 19 | **Upstream Server** | Delete Server | `UpstreamServerRepository.delete()` | `db/upstream_repository.py:129` | Upstream server deleted; aborts pending dispatches to server. | `governance` | YES | `test_upstream_gateway.py` |
| 20 | **Workflow Rules** | Record Rule | `WorkflowRuleRepository.record()` | `db/workflow_rule_repository.py:67` | Workflow transition rule recorded; changes sequence permits. | `governance` | YES | `test_workflow_authority.py` |
| 21 | **Workflow Rules** | Delete Rule | `WorkflowRuleRepository.delete()` | `db/workflow_rule_repository.py:92` | Workflow rule deleted; invalidates queued sequence actions. | `governance` | YES | `test_workflow_authority.py` |
| 22 | **Intent Contract** | Record Intent | `IntentContractRepository.record()` | `db/intent_repository.py:58` | Consequential intent contract recorded; alters intent binding. | `governance` | YES | `test_intent_contract.py` |
| 23 | **IAM Transfer** | Complete Transfer | `OrgOwnershipTransferService.complete_transfer()` | `iam/transfer.py:101` | Org ownership transferred; revokes prior owner's permits. | `governance` + `iam_session` | YES | `test_governance_api.py` |
| 24 | **IAM Recovery** | Complete Recovery | `BreakGlassRecoveryService.complete_recovery()` | `iam/recovery.py:316` | Emergency break-glass access recovered; revokes all permits. | `governance` + `iam_session` | YES | `test_governance_api.py` |
| 25 | **IAM Session** | Revoke Session | `SessionService.revoke_session()` | `iam/session.py:122` | Session explicitly terminated (Pass 4.4 adaptation bumps governance). | `governance` + `iam_session` | YES | `test_governance_api.py` |
| 26 | **IAM BreakGlass** | Terminate Session | `BreakGlassService.terminate_session()` | `iam/break_glass.py` | Emergency BreakGlass session terminated (Pass 4.4 adaptation). | `governance` | YES | `test_governance_api.py` |

---

## 3. Atomic Linearization Guarantee

By guaranteeing that all 26 audited authority mutations advance `governance_revocation_epochs.epoch` under a row lock in the same database transaction:
1. **Zero TOCTOU Window:** No separate, racy "preflight check" is needed as the ultimate security boundary. The canonical admission database transaction is the singular, non-bypassable linearization point.
2. **Deterministic Rejection:** If an authorization was issued at epoch `N`, and ANY authority mutation occurred while the authorization waited in queue, the database epoch becomes `N+1`.
3. **Fail-Closed Admission:** In `ExecutionNonceRepository.consume()`:
   ```sql
   SELECT epoch FROM governance_revocation_epochs
   WHERE organization_id = :org_id AND scope = 'governance'
   FOR UPDATE;
   ```
   If `current_epoch != expected_epoch`, the transaction immediately aborts with `StaleRevocationEpochError`. No nonce is consumed; no execution is admitted.
