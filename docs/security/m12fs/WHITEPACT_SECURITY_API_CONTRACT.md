# WHITEPACT — SECURITY API SPECIFICATION & REST CONTRACT
## Milestone M12-FS Deliverable 8: Authority & Root Hardening REST Endpoints

**Classification:** Security Architecture & API Specification  
**Milestone:** M12-FS (Founder Security Policy Implementation & Root-of-Trust Hardening)  
**Author:** Antigravity — Principal Security Architect & Runtime Qualification Lead  
**Reviewer:** GPT-6 — CTO / Security Review Coordinator  
**Status:** IMPLEMENTED & TESTED (Release Gate: GLOBAL PRODUCTION NO-GO)  

---

### 1. COMMON PROTOCOL CONVENTIONS

#### Authentication & Context Headers
All requests must supply authenticated actor context (verified upstream by the API Gateway or session middleware):
- `X-Actor-Id`: Unique identifier of the authenticated caller (e.g. `user_2xP...`).
- `X-Org-Id`: Tenant organization ID (e.g. `org_9qL...`).
- `X-Role`: Caller's verified role within the organization (`OWNER`, `ADMIN`, `MEMBER`).
- `Content-Type`: `application/json`.

#### Error Envelope
All error responses adhere to the standard WhitePact error envelope:
```json
{
  "error": {
    "code": "ERROR_CODE_CONSTANT",
    "message": "Human-readable description of error.",
    "status_code": 400,
    "details": {}
  }
}
```

---

### 2. ENDPOINT SPECIFICATIONS

#### 2.1 WebAuthn Step-Up Challenge
- **Path:** `POST /api/v1/authority/webauthn/challenge`
- **Description:** Generates a short-lived cryptographic challenge bound to a canonical operation digest.
- **Request Body:**
  ```json
  {
    "operation_type": "BOOTSTRAP",
    "target_id": "org_enterprise_1",
    "ttl_seconds": 300
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "challenge": "base64url_encoded_challenge",
    "challenge_hash": "sha256_hex_digest",
    "rp_id": "auth.whitepact.io",
    "expires_at": "2026-10-15T14:35:00Z"
  }
  ```

---

#### 2.2 Customer Root Bootstrap Initiate
- **Path:** `POST /api/v1/authority/bootstrap/initiate`
- **Description:** Initiates canonical customer root authority creation.
- **Request Body:**
  ```json
  {
    "organization_id": "org_enterprise_1",
    "require_passkey_stepup": true
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "bootstrap_token": "wp_bt_9a8f...",
    "nonce": "c928a47b...",
    "expires_at": "2026-10-15T14:40:00Z",
    "require_passkey_stepup": true
  }
  ```

---

#### 2.3 Customer Root Bootstrap Complete
- **Path:** `POST /api/v1/authority/bootstrap/complete`
- **Description:** Completes root establishment, verifying token, WebAuthn assertion, and Root PoP.
- **Request Body:**
  ```json
  {
    "organization_id": "org_enterprise_1",
    "bootstrap_token": "wp_bt_9a8f...",
    "nonce": "c928a47b...",
    "root_public_key": "32_byte_hex_ed25519_pubkey",
    "pop_signature": "64_byte_hex_ed25519_signature",
    "webauthn_assertion": {
      "credential_id": "cred_id_base64",
      "authenticator_data": "auth_data_base64",
      "client_data_json": "client_data_base64",
      "signature": "sig_base64",
      "challenge_hash": "sha256_hex_digest"
    }
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "COMPLETED",
    "organization_id": "org_enterprise_1",
    "root_authority_id": "auth_root_org_enterprise_1",
    "root_public_key": "32_byte_hex_ed25519_pubkey",
    "created_at": "2026-10-15T14:32:00Z"
  }
  ```

---

#### 2.4 Customer Root Bootstrap Reconcile
- **Path:** `POST /api/v1/authority/bootstrap/reconcile`
- **Description:** Deterministic read-only lookup to resolve ambiguous commit outcomes without token re-issuance.
- **Request Body:**
  ```json
  {
    "organization_id": "org_enterprise_1"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "COMPLETED",
    "organization_id": "org_enterprise_1",
    "root_authority_id": "auth_root_org_enterprise_1",
    "completed_at": "2026-10-15T14:32:00Z"
  }
  ```

---

#### 2.5 Single-Owner Emergency Containment (Decision B)
- **Path:** `POST /api/v1/authority/containment/emergency`
- **Description:** Immediate kill-switch executing agent quarantine, org lockdown, and epoch invalidation.
- **Request Body:**
  ```json
  {
    "organization_id": "org_enterprise_1",
    "target_type": "AGENT",
    "target_id": "agt_sec_ops_1",
    "reason": "Suspected anomalous egress and exfiltration loop."
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "containment_id": "cnt_9a87...",
    "organization_id": "org_enterprise_1",
    "target_type": "AGENT",
    "target_id": "agt_sec_ops_1",
    "status": "CONTAINED",
    "contained_at": "2026-10-15T14:33:00Z"
  }
  ```

---

#### 2.6 Multi-Admin Quorum Recovery (Decision B)
- **Create Request:** `POST /api/v1/authority/recovery/requests`
  - Body: `{ "operation_type": "ROOT_RECOVERY", "target_id": "org_enterprise_1", "quorum_threshold": 2, "total_signers": 3, "recovery_payload": { ... } }`
  - Response: `{ "request_id": "rec_req_1", "operation_digest": "sha256...", "status": "PENDING" }`

- **Cast Vote:** `POST /api/v1/authority/recovery/requests/{request_id}/vote`
  - Body: `{ "decision": "APPROVE", "justification": "Verified out-of-band with admin team." }`
  - Response: `{ "request_id": "rec_req_1", "status": "PENDING", "current_approvals": 2, "required_quorum": 2 }`

- **Execute Request:** `POST /api/v1/authority/recovery/requests/{request_id}/execute`
  - Body: `{}`
  - Response: `{ "request_id": "rec_req_1", "status": "EXECUTED", "executed_at": "2026-10-15T14:36:00Z" }`

- **Get Request:** `GET /api/v1/authority/recovery/requests/{request_id}`
  - Response: `{ "request_id": "rec_req_1", "status": "EXECUTED", "votes": [ ... ] }`

---

### 3. ERROR CODES & MAPPING

| Error Code | HTTP Status | Root Cause |
| :--- | :--- | :--- |
| `PASSKEY_STEP_UP_REQUIRED` | 403 Forbidden | Bootstrap requires WebAuthn step-up assertion but none was provided. |
| `WEBAUTHN_ASSERTION_INVALID` | 400 Bad Request | Signature, authenticatorData flags (`UP=0` or `UV=0`), or clientDataJSON invalid. |
| `WEBAUTHN_CHALLENGE_EXPIRED` | 400 Bad Request | Step-up challenge expired prior to assertion submission. |
| `WEBAUTHN_CHALLENGE_REPLAY` | 409 Conflict | Step-up challenge was already consumed in a prior request. |
| `PROOF_OF_POSSESSION_INVALID`| 400 Bad Request | Ed25519 PoP signature verification failed over ceremony parameters. |
| `CONTAINMENT_FORBIDDEN` | 403 Forbidden | Caller lacks administrative role to execute emergency containment. |
| `CONTAINMENT_INVALID_TARGET` | 400 Bad Request | Invalid target type or target does not belong to caller's organization. |
| `SELF_APPROVAL_BLOCKED` | 403 Forbidden | Request initiator attempted to vote on their own quorum proposal. |
| `ALREADY_VOTED` | 409 Conflict | Admin already submitted a vote for this recovery request. |
| `QUORUM_NOT_MET` | 403 Forbidden | Vote count below threshold or approving voter is no longer an active member. |
| `RECOVERY_EXPIRED` | 400 Bad Request | Recovery proposal expired before reaching quorum. |
| `RECOVERY_ALREADY_EXECUTED` | 409 Conflict | Recovery request has already been executed. |
| `RECOVERY_DIGEST_MISMATCH` | 400 Bad Request | Execution payload does not match the bound canonical digest. |

---

### 4. RELEASE GATE DIRECTIVE

**GLOBAL PRODUCTION NO-GO**: The API contract is fully specified and live in the test suite. External access remains disabled until M13 deployment qualification.
