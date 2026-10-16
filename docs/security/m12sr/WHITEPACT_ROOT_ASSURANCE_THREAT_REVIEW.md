# WHITEPACT — ROOT ASSURANCE THREAT REVIEW
## ADVERSARIAL PENETRATION & THREAT MODELING OF THE TWO-STEP BOOTSTRAP CEREMONY

- **Author:** Antigravity (Principal Security Architect)
- **Target Subsystem:** Customer Root Authority Bootstrap & Trust Fabric Bridge
- **Endpoint Reference:**
  - `POST /api/enterprise/organizations/{org_id}/authority/bootstrap/initiate`
  - `POST /api/enterprise/organizations/{org_id}/authority/bootstrap/complete`
- **Security Baseline:** Milestone M12-SR (`0daa57aa`)

---

## 1. THREAT MODEL & SECURITY BOUNDARIES

The WhitePact customer authority lifecycle establishes the root-of-trust from which all subsequent agent delegations, policy evaluations, and execution grants derive.

### Critical Distinction: Registered Ownership vs. Strong Identity Assurance
> **Cautionary Architectural Notice:**
> A standard email-verified organization owner authenticated solely via username/password session cookies represents **registered ownership**, NOT **cryptographic or hardware identity assurance**.
>
> While the two-step ceremony provides strong transport security, CSRF defense, single-use anti-replay, and temporal bound enforcement, it remains vulnerable to local session hijacking or endpoint compromise unless backed by **phishing-resistant WebAuthn / FIDO2 hardware credentials or qualified enterprise federation**.

---

## 2. ADVERSARIAL ATTACK MATRIX & EMPIRICAL FINDINGS

Each potential attack vector against the customer root authority lifecycle was independently analyzed and tested:

### 2.1. Registration Without Verified Ownership
- **Attack Vector:** An unverified user or user with non-OWNER membership calls bootstrap endpoints.
- **Defense Mechanism:** `CustomerAuthorityService._verify_tenant_and_role(actor, org_id, require_owner=True)` verifies that `actor.role == Role.OWNER` and `web_users.email_verified_at` is set.
- **Empirical Result:** **FAIL-CLOSED (HTTP 403 UNAUTHORIZED_BOOTSTRAP_CALLER)**.

### 2.2. Cross-Tenant Injection
- **Attack Vector:** An authenticated owner of Organization A attempts to initiate or complete bootstrap for Organization B by manipulating the URL path `{org_id}`.
- **Defense Mechanism:** The authenticated session resolves `actor.org_id`. The router asserts `actor.org_id == org_id`.
- **Empirical Result:** **FAIL-CLOSED (HTTP 403 CROSS_TENANT)**. Verified in `test_cross_tenant_bootstrap_rejected`.

### 2.3. Cross-Site Request Forgery (CSRF)
- **Attack Vector:** Attacker lures owner to a malicious webpage that triggers a cross-origin POST request to initiate or complete bootstrap.
- **Defense Mechanism:** Dual-cookie CSRF defense requires both cookie `wp_csrf` and custom header `X-WP-CSRF` matching the session's SHA-256 CSRF hash.
- **Empirical Result:** **FAIL-CLOSED (HTTP 403 CSRF_REQUIRED / CSRF_INVALID)**. Verified in `test_csrf_protection_enforced`.

### 2.4. Session Fixation & Stolen Sessions
- **Attack Vector:** Attacker captures an inactive or pre-auth session token to hijack the bootstrap flow.
- **Defense Mechanism:** WebIdentityRepository rotates session tokens upon login and binds sessions to unique IDs with inactivity timeouts.
- **Empirical Result:** **FAIL-CLOSED**. Invalid or expired sessions yield HTTP 401 UNAUTHENTICATED.

### 2.5. Bootstrap Token Theft (Within Same Organization)
- **Attack Vector:** User A (Owner) initiates bootstrap. User B (also an Owner/Admin in the same org) intercepts the token and attempts to complete the ceremony to bind their own public key.
- **Defense Mechanism:** During initiation, `claimed_by_principal_id` is set to `actor.user_id`. During completion, the service checks:
  ```python
  if rec.get("claimed_by_principal_id") and rec["claimed_by_principal_id"] != actor.user_id:
      raise unauthorized_caller("Ceremony is bound to principal..., cannot be claimed by...")
  ```
- **Empirical Result:** **FAIL-CLOSED (HTTP 403 UNAUTHORIZED_BOOTSTRAP_CALLER)**. Verified in `test_stolen_bootstrap_token_fails_closed`.

### 2.6. Nonce Tampering & Substitution
- **Attack Vector:** Attacker supplies a valid ceremony token with a forged or substituted nonce.
- **Defense Mechanism:** Record lookup requires exact matching `nonce` AND constant-time hash comparison (`secrets.compare_digest(rec["token_hash"], token_hash)`).
- **Empirical Result:** **FAIL-CLOSED (HTTP 403 BOOTSTRAP_TOKEN_INVALID)**. Verified in `test_nonce_substitution_rejected`.

### 2.7. Temporal Expiration (TTL Enforcement)
- **Attack Vector:** An attacker attempts to complete an expired bootstrap challenge.
- **Defense Mechanism:** Ceremony records enforce server-side expiration: `if now_iso >= rec["expires_at"]: raise bootstrap_expired(...)`. Router rejects requests with TTL outside 60s–86400s (`ge=60, le=86400`).
- **Empirical Result:** **FAIL-CLOSED (HTTP 403 BOOTSTRAP_TOKEN_EXPIRED)**. Verified in `test_expired_bootstrap_token_rejected`.

### 2.8. Replay Attacks
- **Attack Vector:** Re-submitting a previously completed ceremony request to overwrite or replace root keys.
- **Defense Mechanism:** Upon successful completion, `consumed_at` is immediately written to the database in the same transaction. Subsequent requests detect `consumed_at IS NOT NULL`.
- **Empirical Result:** **FAIL-CLOSED (HTTP 409 BOOTSTRAP_TOKEN_REPLAY)**. Verified in `test_replayed_bootstrap_token_rejected`.

### 2.9. Concurrent Bootstrap Race Conditions
- **Attack Vector:** Two owners simultaneously submit bootstrap completion requests to create conflicting root records.
- **Defense Mechanism:** `lock_epoch(conn, org_id)` acquires an exclusive row lock on the organization's revocation epoch. The second transaction blocks, detects existing active root authority, and aborts.
- **Empirical Result:** **SINGLE WINNER (HTTP 200 Winner, HTTP 409 ROOT_ALREADY_EXISTS Loser)**. Verified in `test_concurrent_bootstrap_attempts_single_winner`.

### 2.10. Empty or Unbounded Consent Omission
- **Attack Vector:** Client attempts to establish root authority without specifying bounded action types or target scopes.
- **Defense Mechanism:** `complete_root_bootstrap` asserts that `allowed_action_types` and `allowed_targets` are non-empty lists.
- **Empirical Result:** **FAIL-CLOSED (HTTP 400 CONSENT_PARAMETERS_INVALID)**. Verified in `test_empty_consent_fails_closed`.

### 2.11. Database Commit Ambiguity
- **Attack Vector:** Network drop or connection reset occurs after database transaction begins.
- **Defense Mechanism:** All state transitions—consuming the bootstrap record, inserting canonical governance root, and inserting consent proof—occur in a single ACID transaction (`async with self._engine.raw.begin()`). If the connection drops before commit, the entire ceremony rolls back cleanly.

### 2.12. Malicious Administrators & Unauthorized Consent Expansion
- **Attack Vector:** Non-owner administrator attempts to expand the scope of consent or delegate permissions outside the customer's accepted consent proof.
- **Defense Mechanism:** The AuthorityResolver evaluates every downstream action against the root consent proof. Delegations cannot grant permissions exceeding the parent's consent boundary (strict attenuation). Non-owners cannot modify root authority.

---

## 3. IDENTIFIED RESIDUAL THREATS & MITIGATION PATHWAY

1. **Compromised Owner Endpoint / Credential Stuffing:**
   - *Risk:* If an attacker compromises the owner's password and email, they can register sessions and complete bootstrap.
   - *Mitigation:* Founder Decision A mandates phishing-resistant WebAuthn/passkey hardware step-up before root issuance can be triggered in production.
2. **Denial-of-Service via Repeated Initiation:**
   - *Risk:* An owner repeatedly calling `/bootstrap/initiate` overwrites the active ceremony record.
   - *Mitigation:* Rate limiting via `slowapi` (`@limiter.limit("5/minute")`) and serial lock on tenant epoch.

---

## 4. CONCLUSION

The WhitePact M12-SR customer root bootstrap lifecycle successfully withstands all tested adversarial attack scenarios and conforms to fail-closed security invariants. Production enablement is conditionally gated on Founder Decision A (WebAuthn hardware assurance).
