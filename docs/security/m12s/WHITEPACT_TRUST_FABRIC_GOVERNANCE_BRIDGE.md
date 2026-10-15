# WHITEPACT — TRUST FABRIC TO CANONICAL GOVERNANCE BRIDGE

**Document ID:** WP-M12S-BRIDGE-003  
**Classification:** ARCHITECTURAL SPECIFICATION & SECURITY AUDIT  
**Audience:** Codex Product Engineering, Security Architecture, Runtime Leads  
**Module:** `responsibleai.enterprise.authority.service`  
**Status:** IMPLEMENTED & AUDITED

---

## 1. TRUST FABRIC SECURITY AUDIT FINDINGS

Prior to Milestone M12-S, the WhitePact codebase possessed two parallel, disconnected authority mechanisms:
1. **Trust Fabric Substrate (`responsibleai.trust_fabric`):** A tenant identity and principal registry that tracked principals, keys, and an internal bootstrap ceremony, but did not interface with the canonical governance kernel.
2. **Canonical Governance Kernel (`responsibleai.governance`):** A strict cryptographic authority evaluator (`AuthorityResolver`) backed by `RootAuthorityRepository`, `ConsentProofRepository`, and `DelegationRepository`.

### Critical Flaws Discovered in Pre-M12 Audit:
- **Missing Customer Bridge:** No authenticated, customer-facing HTTP pathway existed to bridge Trust Fabric roots into `governance_root_authority_records` and `governance_consent_proofs`.
- **Identity Equivocation:** A user or agent record in Trust Fabric could be misconstrued as holding execution authority.
- **Disconnected Revocation Epochs:** Trust Fabric mutations did not reliably synchronize with `revocation_epoch` in `governance_revocation_epochs`.

---

## 2. THE CANONICAL UNIFIED BRIDGE ARCHITECTURE

The M12-S `CustomerAuthorityService` establishes **one canonical bridge** between Trust Fabric and the Canonical Governance Kernel, eliminating duplicate authority kernels and ensuring strict transactional consistency.

```
                           +----------------------------------------+
                           |       Authenticated Customer Owner      |
                           +----------------------------------------+
                                               |
                                               | 1. Initiate Ceremony (token + nonce)
                                               | 2. Submit Root PK + Explicit Scoped Consent
                                               v
+----------------------------------------------------------------------------------------------------+
|                         CustomerAuthorityService.complete_root_bootstrap()                         |
|                                       (Atomic DB Transaction)                                      |
|                                                                                                    |
|  [Lock & Read Epoch] ----> [Consume Token/Nonce] ----> [Update Trust Fabric Root]                  |
|                                                                    |                               |
|                                                                    v                               |
|  [Bump Revocation Epoch] <-- [Mint Canonical ConsentProof] <-- [Mint Canonical RootAuthorityRecord] |
|            |                                                               |                       |
|            +------------------------------+--------------------------------+                       |
|                                           |                                                        |
|                                           v                                                        |
|                           [Emit Immutable Enterprise Audit Log]                                    |
+----------------------------------------------------------------------------------------------------+
                                            |
                                            | Verified Chain Available To:
                                            v
+----------------------------------------------------------------------------------------------------+
|                                    AuthorityResolver.resolve()                                     |
|                                                                                                    |
|  1. Validate Tenant & Context Binding                                                              |
|  2. Load Latest ConsentProof for Grantee (Verify SHA-256 Digest & Temporal Expiry)                 |
|  3. Validate RootAuthorityRecord (Verify Cryptographic Digest & Issuer)                            |
|  4. Traverse Delegation Chain to Root Subject (Validate Zero Cycles & Invariant Attenuation)      |
|  5. Check Revocation Epoch (Fail Closed on Any Drift)                                              |
|  6. Issue Short-Lived Single-Use ExecutionAuthorization                                            |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. AUDIT QUESTIONNAIRE & VERIFIED ANSWERS

### 1. Who issues identities?
- **Answer:** Identities (`trust_fabric_principals`) are issued exclusively by authenticated organization administrators or owners via `CustomerAuthorityService.register_agent()` or verified user registration flows. An agent cannot self-register or self-issue.

### 2. How is owner identity established?
- **Answer:** Owner identity is verified via server-side session authentication (`Actor`), authenticated through enterprise SSO (SAML/OIDC) or verified email password sessions with role `Role.OWNER` in `web_users`. The client has zero ability to assert owner status.

### 3. Is tenant context trustworthy?
- **Answer:** Yes. In all authority endpoints, `actor.org_id` is extracted from verified session cookies/tokens. If the request URL path or payload contains an `org_id` different from `actor.org_id`, `_verify_tenant_and_role` immediately aborts with `403 Forbidden (CROSS_TENANT)`.

### 4. Where does consent originate?
- **Answer:** Consent originates exclusively from the explicit parameters (`scope_description`, `purpose`, `allowed_action_types`, `allowed_targets`, `evidence_refs`) submitted by the verified owner during `complete_root_bootstrap` or `delegate_to_agent`. It cannot be synthesized or inferred.

### 5. Which service is allowed to mint roots?
- **Answer:** Only `CustomerAuthorityService.complete_root_bootstrap()` is permitted to insert rows into `governance_root_authority_records` and `trust_fabric_trust_roots`. Direct SQL insertion or arbitrary API calls are structurally blocked.

### 6. How is root authority verified?
- **Answer:** `AuthorityResolver` loads the record from PostgreSQL, recomputes the SHA-256 `compute_root_digest()`, validates that `revoked_at IS NULL`, checks `not_before <= now <= expires_at`, verifies evidence references, and ensures `current.organization_id == context.organization_id`.

### 7. Can authority be broadened?
- **Answer:** No. Every downward delegation is strictly validated via `validate_attenuation(parent, child)`. A child delegation cannot introduce new action types, expand target patterns, or outlive the parent. Any escalation attempt raises `AuthorityDenied("DELEGATION_ESCALATION")`.

### 8. How are keys rotated?
- **Answer:** Key rotation is executed by invoking `revoke_root_authority()`, which invalidates the current root and cascades revocation to all delegations. A new ceremony is then initiated via `initiate_root_bootstrap()`.

### 9. How does revocation propagate?
- **Answer:** Revocation is instantaneous and atomic. In a single transaction under an epoch row-lock, the database marks the root record as revoked, marks all associated consent proofs as revoked, sets `trust_fabric_trust_roots.status = 'REVOKED'`, revokes all organization delegations, and increments `revocation_epoch`. Any cached or in-flight permits fail instantly on epoch mismatch.

### 10. How does recovery work?
- **Answer:** If a ceremony is interrupted or times out before consumption, the expired record can be safely overwritten by a new `initiate_root_bootstrap` call by the owner. If a root key is compromised, an immediate call to `revoke_root_authority` shuts down all tenant execution in <50ms.
