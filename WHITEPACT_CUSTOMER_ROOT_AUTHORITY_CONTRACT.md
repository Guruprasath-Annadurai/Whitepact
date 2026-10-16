# WHITEPACT — CUSTOMER ROOT AUTHORITY & CONSENT BACKEND CONTRACT

**Document ID:** WP-M12S-CONTRACT-002  
**Classification:** NORMATIVE API & SECURITY SPECIFICATION  
**Audience:** Codex Product Engineering, SDK Leads, Antigravity Security  
**Status:** IMPLEMENTED & VERIFIED ON POSTGRESQL 16  
**Module:** `responsibleai.enterprise.authority`  
**Base Path:** `/api/enterprise/organizations/{org_id}/authority`

---

## 1. PURPOSE & ARCHITECTURAL INVARIANTS

This specification defines the normative backend contract for customer root authority bootstrap, explicit scoped consent, and agent delegation within WhitePact.

### Constitutional Rules:
1. **Server-Derivation of Authority:** Tenant ID (`org_id`), root principal ID, and authority identities are derived strictly from authenticated server-side session credentials (`Actor`). The client cannot choose or override tenant identity.
2. **Registration != Authority:** Creating an organization or registering an agent does not confer runtime execution capability. Authority requires an unbroken, cryptographically bound delegation chain rooted in an explicit customer consent proof.
3. **Replay Resistance:** Bootstrap ceremonies use single-use server-issued tokens and nonces with mandatory TTL expiry.
4. **No Client-Minted Root Records:** The browser/client never submits raw `RootAuthorityRecord` or `ConsentProof` objects; these are minted exclusively by `CustomerAuthorityService` in an atomic database transaction.

---

## 2. STATE MACHINE & LIFECYCLE

```
                +---------------------+
                |    UNINITIALIZED    |
                +---------------------+
                           |
                           | POST /bootstrap/initiate (Owner Only)
                           v
                +---------------------+
                |  CEREMONY_PENDING   |  (TTL: 900s)
                +---------------------+
                           |
                           | POST /bootstrap/complete (Owner + Token + Scoped Consent)
                           v
                +---------------------+
                |       ACTIVE        |  <-- Epoch: 1
                +---------------------+
                     |             |
     POST /agents    |             | POST /root/{root_id}/revoke (Owner)
     POST /delegations             v
                     |    +---------------------+
                     +--> |       REVOKED       |  <-- Epoch: 2+ (Cascading closed)
                          +---------------------+
```

---

## 3. ENDPOINT SPECIFICATIONS

### 3.1 Initiate Bootstrap Ceremony
- **Method / Path:** `POST /api/enterprise/organizations/{org_id}/authority/bootstrap/initiate`
- **Auth Required:** Authenticated User with Role `OWNER` in tenant `{org_id}`.
- **CSRF Protection:** Required (`X-WP-CSRF` header matching `wp_csrf` cookie).
- **Request Body:**
  ```json
  {
    "ttl_seconds": 900
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "ceremony_id": "wp_brec_a1b2c3d4e5f6...",
    "organization_id": "org_uuid_here",
    "token": "wp_boot_s0m3_s3cr3t_url_s4f3_str1ng...",
    "nonce": "wp_nonce_4f7e2a9b...",
    "expires_at": "2026-10-15T10:45:00.000000+00:00",
    "bound_owner_id": "usr_uuid_here"
  }
  ```
- **Errors:**
  - `400 Bad Request`: `BOOTSTRAP_INVALID` (active root already exists or invalid TTL)
  - `403 Forbidden`: `UNAUTHORIZED_CALLER` (caller is not verified OWNER) or `CROSS_TENANT`

---

### 3.2 Complete Bootstrap Ceremony
- **Method / Path:** `POST /api/enterprise/organizations/{org_id}/authority/bootstrap/complete`
- **Auth Required:** Authenticated User with Role `OWNER` in tenant `{org_id}`.
- **Request Body:**
  ```json
  {
    "token": "wp_boot_s0m3_s3cr3t_url_s4f3_str1ng...",
    "nonce": "wp_nonce_4f7e2a9b...",
    "root_public_key": "ed25519_pk_enterprise_customer_root_001",
    "scope_description": "Authorizes automated invoice reconciliation and ledger audit agents",
    "purpose": "invoice-reconciliation",
    "allowed_action_types": ["invoice:read", "invoice:match"],
    "allowed_targets": ["invoices/2026/001", "invoices/2026/002"],
    "key_algorithm": "Ed25519",
    "consent_method": "CRYPTOGRAPHIC_CEREMONY",
    "evidence_refs": ["board_resolution_2026_09", "ciso_approval_ceremony"]
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "BOOTSTRAPPED",
    "organization_id": "org_uuid_here",
    "root_id": "root_uuid_here",
    "subject_id": "usr_uuid_here",
    "consent_id": "consent_uuid_here",
    "purpose": "invoice-reconciliation",
    "allowed_action_types": ["invoice:match", "invoice:read"],
    "allowed_targets": ["invoices/2026/001", "invoices/2026/002"],
    "epoch": 1,
    "established_at": "2026-10-15T10:30:00.000000+00:00"
  }
  ```
- **Errors:**
  - `400 Bad Request`: `BOOTSTRAP_INVALID` / `CONSENT_INVALID` (empty scope/action types/targets)
  - `401 Unauthorized`: `BOOTSTRAP_EXPIRED` (ceremony TTL elapsed) or `UNAUTHORIZED_CALLER` (wrong user)
  - `409 Conflict`: `BOOTSTRAP_REPLAY` (token already consumed) or `ROOT_ALREADY_EXISTS` (concurrent race)

---

### 3.3 Query Authority Status
- **Method / Path:** `GET /api/enterprise/organizations/{org_id}/authority/status`
- **Auth Required:** Authenticated Member (Role `OWNER`, `ADMIN`, or `ANALYST`) in tenant `{org_id}`.
- **Response (200 OK):**
  ```json
  {
    "organization_id": "org_uuid_here",
    "has_active_authority": true,
    "root_authority": {
      "root_id": "root_uuid_here",
      "subject_id": "usr_uuid_here",
      "root_type": "human",
      "issuer": "customer:usr_uuid_here",
      "verification_method": "customer_bootstrap_ceremony",
      "jurisdiction": "enterprise",
      "issued_at": "2026-10-15T10:30:00.000000+00:00",
      "canonical_digest": "sha256_hash_here..."
    },
    "consent_proof": {
      "consent_id": "consent_uuid_here",
      "purpose": "invoice-reconciliation",
      "scope_description": "Authorizes automated invoice reconciliation and ledger audit agents",
      "consent_method": "SIGNED_DOCUMENT",
      "allowed_action_types": ["invoice:match", "invoice:read"],
      "allowed_targets": ["invoices/2026/001", "invoices/2026/002"],
      "consented_at": "2026-10-15T10:30:00.000000+00:00",
      "canonical_digest": "sha256_hash_here..."
    },
    "revocation_epoch": 1
  }
  ```

---

### 3.4 Revoke Root Authority
- **Method / Path:** `POST /api/enterprise/organizations/{org_id}/authority/root/{root_id}/revoke`
- **Auth Required:** Authenticated User with Role `OWNER` in tenant `{org_id}`.
- **Request Body:**
  ```json
  {
    "reason": "Customer security key rollover"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "REVOKED",
    "root_id": "root_uuid_here",
    "organization_id": "org_uuid_here",
    "new_epoch": 2,
    "revoked_at": "2026-10-15T10:35:00.000000+00:00",
    "revoked_by": "usr_uuid_here"
  }
  ```
- **Atomicity & Cascading Effect:**
  In a single PostgreSQL transaction with `SELECT ... FOR UPDATE` on `revocation_epoch`:
  1. `revocation_epoch` increments from `N` to `N+1`.
  2. `governance_root_authority_records` marks `revoked_at=now`.
  3. `governance_consent_proofs` marks `revoked_at=now` for all proofs under this root.
  4. `trust_fabric_trust_roots` marks `status='REVOKED'`.
  5. `governance_delegations` marks `revoked_at=now` for all delegations in the tenant.
  6. Durable enterprise audit record is committed.

---

### 3.5 Register AI Agent
- **Method / Path:** `POST /api/enterprise/organizations/{org_id}/authority/agents`
- **Auth Required:** Authenticated User with Role `OWNER` or `ADMIN` in tenant `{org_id}`.
- **Request Body:**
  ```json
  {
    "name": "Invoice Reconciliation Agent",
    "description": "Autonomous invoice processing agent",
    "framework": "crewai",
    "purpose": "invoice-reconciliation"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "agent_id": "agent_a72d308c96d4",
    "organization_id": "org_uuid_here",
    "name": "Invoice Reconciliation Agent",
    "framework": "crewai",
    "has_delegated_authority": false,
    "registered_at": "2026-10-15T10:32:00.000000+00:00"
  }
  ```
- **Security Invariant:** `has_delegated_authority` is explicitly `false`. Any action attempted by this agent will be denied by `AuthorityResolver` until delegation is issued.

---

### 3.6 Issue Attenuated Delegation to Agent
- **Method / Path:** `POST /api/enterprise/organizations/{org_id}/authority/agents/{agent_id}/delegations`
- **Auth Required:** Authenticated User with Role `OWNER` or `ADMIN` in tenant `{org_id}`.
- **Request Body:**
  ```json
  {
    "granted_action_types": ["invoice:read"],
    "allowed_targets": ["invoices/2026/001"],
    "purpose": "invoice-reconciliation",
    "expires_at": null
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "delegation_id": "del_uuid_here",
    "consent_id": "consent_uuid_here",
    "agent_id": "agent_a72d308c96d4",
    "organization_id": "org_uuid_here",
    "granted_action_types": ["invoice:read"],
    "allowed_targets": ["invoices/2026/001"],
    "purpose": "invoice-reconciliation",
    "granted_at": "2026-10-15T10:33:00.000000+00:00"
  }
  ```
- **Security Invariants Enforced:**
  1. **Attenuation:** Granted action types must be a subset of parent permissions.
  2. **Zero Epoch Drift:** Uses `lock_epoch()` instead of bumping the revocation epoch.
  3. **Consent Binding:** Automatically issues an explicit `ConsentProof` for `grantee_id == agent_id` bound to the active root authority record.

---

### 3.7 Disable Agent
- **Method / Path:** `POST /api/enterprise/organizations/{org_id}/authority/agents/{agent_id}/disable`
- **Auth Required:** Authenticated User with Role `OWNER` or `ADMIN` in tenant `{org_id}`.
- **Request Body:**
  ```json
  {
    "reason": "Agent decommissioned by administrator"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "DISABLED",
    "agent_id": "agent_a72d308c96d4",
    "organization_id": "org_uuid_here",
    "revoked_delegations": ["del_uuid_here"],
    "new_epoch": 2,
    "disabled_at": "2026-10-15T10:36:00.000000+00:00"
  }
  ```
