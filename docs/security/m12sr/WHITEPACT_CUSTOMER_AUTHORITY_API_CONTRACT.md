# WHITEPACT — CUSTOMER AUTHORITY & AGENT LIFECYCLE API CONTRACT
## SPECIFICATION FOR CODEX FRONTEND, SDK & WORKFLOW INTEGRATION

- **Author:** Antigravity (Principal Security Architect)
- **Target Audience:** Codex Product Engineering, SDK Developers, Dashboard Integrators
- **Base URI:** `/api/enterprise/organizations/{org_id}/authority`
- **Specification Status:** **FROZEN & VERIFIED IN M12-SR**
- **Authentication:** Authenticated Web Session Cookie (`wp_session`) + Dual-Cookie CSRF (`wp_csrf` cookie & `X-WP-CSRF` header).
- **Core Principle:** Clients **cannot** manufacture root records, tokens, or execution grants. All authority is minted and validated exclusively server-side.

---

## 1. ENDPOINT SPECIFICATIONS

### 1.1. Initiate Bootstrap Ceremony
Initiates the two-step root establishment ceremony. Returns a short-lived challenge token and nonce bound to the authenticated owner.

- **Method:** `POST /api/enterprise/organizations/{org_id}/authority/bootstrap/initiate`
- **Required Role:** `OWNER` (Email must be verified)
- **Request Headers:**
  - `Cookie: wp_session=<session_token>; wp_csrf=<csrf_token>`
  - `X-WP-CSRF: <csrf_token>`
  - `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "ttl_seconds": 900,
    "require_identity_assurance": false
  }
  ```
  *Field constraints:*
  - `ttl_seconds` (int, optional): Minimum `60`, maximum `86400`, default `900`.
  - `require_identity_assurance` (bool, optional): Default `false`. If true, requires verified identity status.
- **Success Response (HTTP 200 OK):**
  ```json
  {
    "ceremony_id": "wp_brec_688c227581fe4d989938b02daee9c988",
    "organization_id": "org_3a7b686d-f421-4f1f-9da8-3904e0e9bcbb",
    "token": "wp_boot_s6tN4F1hLq8...",
    "nonce": "wp_nonce_3b8a1c92...",
    "expires_at": "2026-10-15T12:00:00+00:00",
    "bound_owner_id": "usr_42f8b..."
  }
  ```
- **Error Responses:**
  - `401 Unauthorized` (`UNAUTHENTICATED`): Session cookie missing or expired.
  - `403 Forbidden` (`CSRF_REQUIRED` / `CSRF_INVALID`): Missing or mismatched `X-WP-CSRF` header.
  - `403 Forbidden` (`CROSS_TENANT`): Path `org_id` does not match session tenant.
  - `403 Forbidden` (`UNAUTHORIZED_BOOTSTRAP_CALLER`): Caller is not an `OWNER`.
  - `409 Conflict` (`ROOT_ALREADY_EXISTS`): Organization already has an active canonical root authority.

---

### 1.2. Complete Bootstrap Ceremony & Record Explicit Consent
Atomically completes the ceremony, establishes canonical root authority, and records customer-accepted bounded consent proofs.

- **Method:** `POST /api/enterprise/organizations/{org_id}/authority/bootstrap/complete`
- **Required Role:** `OWNER` (Must be the identical owner who initiated the ceremony)
- **Request Body:**
  ```json
  {
    "token": "wp_boot_s6tN4F1hLq8...",
    "nonce": "wp_nonce_3b8a1c92...",
    "root_public_key": "pk_ed25519_customer_root_77f...",
    "key_algorithm": "Ed25519",
    "scope_description": "Production customer authority boundary for financial research agents",
    "purpose": "Financial Analysis & Data Extraction",
    "allowed_action_types": ["tool:read", "database:query", "report:generate"],
    "allowed_targets": ["finance-db/*", "market-data/v1/*"],
    "consent_method": "CRYPTOGRAPHIC_CEREMONY",
    "evidence_refs": ["urn:evidence:audit-log-ref-1"]
  }
  ```
  *Field constraints:*
  - `token`, `nonce`, `root_public_key`: Non-empty strings.
  - `scope_description`: 1 to 1000 characters.
  - `purpose`: 1 to 255 characters.
  - `allowed_action_types`, `allowed_targets`: Non-empty lists of strings.
- **Success Response (HTTP 200 OK):**
  ```json
  {
    "status": "ESTABLISHED",
    "organization_id": "org_3a7b686d-f421-4f1f-9da8-3904e0e9bcbb",
    "root_authority_id": "root_93b2...",
    "consent_proof_id": "cp_17a4...",
    "established_at": "2026-10-15T11:45:00+00:00"
  }
  ```
- **Error Responses:**
  - `400 Bad Request` (`CONSENT_PARAMETERS_INVALID`): Missing or empty consent lists/purpose.
  - `403 Forbidden` (`BOOTSTRAP_TOKEN_INVALID`): Nonce or token hash mismatch.
  - `403 Forbidden` (`BOOTSTRAP_TOKEN_EXPIRED`): Ceremony expiration timestamp passed.
  - `403 Forbidden` (`UNAUTHORIZED_BOOTSTRAP_CALLER`): User claiming ceremony differs from user who initiated.
  - `409 Conflict` (`BOOTSTRAP_TOKEN_REPLAY`): Token/nonce has already been consumed.
  - `409 Conflict` (`ROOT_ALREADY_EXISTS`): Concurrent attempt already established a root.

---

### 1.3. Get Authority & Trust Fabric Status
Inspects the current state of customer root authority, consent proofs, and active agents.

- **Method:** `GET /api/enterprise/organizations/{org_id}/authority/status`
- **Required Role:** `OWNER` or `ADMIN`
- **Success Response (HTTP 200 OK):**
  ```json
  {
    "organization_id": "org_3a7b686d-f421-4f1f-9da8-3904e0e9bcbb",
    "has_canonical_root": true,
    "root_authority": {
      "root_id": "root_93b2...",
      "root_type": "CUSTOMER_DEFINED",
      "status": "ACTIVE",
      "created_at": "2026-10-15T11:45:00+00:00"
    },
    "consent_proof": {
      "proof_id": "cp_17a4...",
      "purpose": "Financial Analysis & Data Extraction",
      "allowed_action_types": ["tool:read", "database:query", "report:generate"],
      "allowed_targets": ["finance-db/*", "market-data/v1/*"]
    },
    "active_agents_count": 2,
    "current_revocation_epoch": 1
  }
  ```

---

### 1.4. Revoke Root Authority
Emergency unilateral kill-switch to revoke customer root authority.

- **Method:** `POST /api/enterprise/organizations/{org_id}/authority/root/{root_id}/revoke`
- **Required Role:** `OWNER`
- **Request Body:**
  ```json
  {
    "reason": "Suspected compromise of development signing key"
  }
  ```
- **Success Response (HTTP 200 OK):**
  ```json
  {
    "status": "REVOKED",
    "root_id": "root_93b2...",
    "revocation_epoch": 2,
    "revoked_at": "2026-10-15T12:05:00+00:00"
  }
  ```

---

### 1.5. Register Agent (Separation of Registration from Authority)
Registers a machine agent entity under the organization. **Note: Registration alone conveys ZERO authority.**

- **Method:** `POST /api/enterprise/organizations/{org_id}/authority/agents`
- **Required Role:** `OWNER` or `ADMIN`
- **Request Body:**
  ```json
  {
    "name": "Financial Summarizer Agent",
    "description": "Extracts quarterly metrics",
    "framework": "LangChain",
    "purpose": "Financial analysis"
  }
  ```
- **Success Response (HTTP 200 OK):**
  ```json
  {
    "agent_id": "ag_18c4...",
    "name": "Financial Summarizer Agent",
    "status": "UNAUTHORIZED_NO_DELEGATION",
    "created_at": "2026-10-15T12:10:00+00:00"
  }
  ```

---

### 1.6. Delegate Attenuated Authority to Agent
Delegates scoped authority from the root authority down to a specific agent.

- **Method:** `POST /api/enterprise/organizations/{org_id}/authority/agents/{agent_id}/delegate`
- **Required Role:** `OWNER`
- **Request Body:**
  ```json
  {
    "granted_action_types": ["tool:read", "database:query"],
    "allowed_targets": ["finance-db/public/*"],
    "purpose": "Quarterly extraction",
    "expires_at": "2026-10-16T12:00:00+00:00"
  }
  ```
  *Attenuation Rule:* `granted_action_types` and `allowed_targets` MUST be a strict subset of the customer root consent scope. Any action outside root consent fails closed (`DELEGATION_ATTENUATION_VIOLATION`).

---

### 1.7. Disable Agent
Immediately revokes all delegated authority for an individual agent.

- **Method:** `POST /api/enterprise/organizations/{org_id}/authority/agents/{agent_id}/disable`
- **Required Role:** `OWNER` or `ADMIN`
- **Request Body:**
  ```json
  {
    "reason": "Scheduled maintenance deprovisioning"
  }
  ```
- **Success Response (HTTP 200 OK):**
  ```json
  {
    "status": "DISABLED",
    "agent_id": "ag_18c4...",
    "disabled_at": "2026-10-15T12:15:00+00:00"
  }
  ```

---

## 2. CLIENT INTEGRATION RULES

1. **Never retry UNKNOWN automatically:** If a network timeout or HTTP 500/504 occurs during `complete`, query `GET /status` to determine if the transaction committed. Blind retries will fail with `BOOTSTRAP_TOKEN_REPLAY` if committed, or consume rate limits.
2. **Display Exact Consent Parameters:** The UI must display the precise `allowed_action_types`, `allowed_targets`, and `purpose` before the user accepts the ceremony.
3. **Handle 403 UNAUTHORIZED_BOOTSTRAP_CALLER Gracefully:** Inform the user that root ceremonies require Organization Owner privileges.
