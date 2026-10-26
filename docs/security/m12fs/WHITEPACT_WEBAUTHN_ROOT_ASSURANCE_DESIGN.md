# WHITEPACT — WEBAUTHN ROOT ASSURANCE DESIGN (M12-FS)

**Document ID:** WP-M12FS-SEC-002  
**Milestone:** M12-FS  
**Component:** Enterprise Authentication & Authority Kernel  
**Standards Compliance:** W3C WebAuthn Level 3, FIDO2, RFC 8174  
**Release Gate:** GLOBAL PRODUCTION NO-GO  

---

## 1. Overview & Objectives

Founder Decision A mandates phishing-resistant authentication for privileged root-authority establishment and high-risk governance mutations.

WhitePact rejects bearer sessions, API keys, passwords, SMS OTPs, and email confirmation links as insufficient for root-of-trust operations. Mere possession of an active session cookie does not satisfy root establishment criteria.

The WebAuthn Root Assurance subsystem ensures that:
1. Every ceremony requires a server-minted, cryptographically bound, replay-protected challenge.
2. The ceremony explicitly verifies **User Presence (`UP=0x01`)** and **User Verification (`UV=0x04`)**.
3. The WebAuthn assertion signature is strictly bound to the canonical operation digest.
4. Passkey credential types (multi-device synced passkeys vs. hardware-bound security keys) are accurately distinguished via attestation flags rather than false universal claims.

---

## 2. Protocol & Architecture Flow

```
+----------------------------------------------------------------------------------------------------+
|                                      WEBAUTHN STEP-UP CEREMONY                                      |
+----------------------------------------------------------------------------------------------------+
  Customer Client                     Authority REST API                     Database / Kernel
        |                                     |                                      |
        | 1. Compute Canonical Op Digest      |                                      |
        |    sha256(action, params)           |                                      |
        |------------------------------------>|                                      |
        |    POST /webauthn/challenge         |                                      |
        |    {action, operation_digest}       | 2. Generate 32-byte secure challenge |
        |                                     |    Insert into step_up_challenges    |
        |                                     |------------------------------------->|
        |                                     |    (challenge_hash, expires_at)      |
        | 3. Receive Challenge & RP ID        |<-------------------------------------|
        |<------------------------------------|                                      |
        |                                     |                                      |
        | 4. Prompt Passkey Authenticator     |                                      |
        |    (UP=1, UV=1 via Biometric/PIN)   |                                      |
        |    Signs (auth_data || client_hash) |                                      |
        |                                     |                                      |
        | 5. Submit Complete Ceremony         |                                      |
        |------------------------------------>|                                      |
        |    POST /bootstrap/complete         | 6. Atomic DB Lock & Verification     |
        |    {webauthn_assertion, token, ...} |    - Verify challenge unconsumed     |
        |                                     |    - Compare operation_digest        |
        |                                     |    - Mark challenge consumed         |
        |                                     |    - Verify ES256 ECDSA signature    |
        |                                     |    - Validate UP=1 and UV=1          |
        |                                     |    - Validate sign_count advancement |
        |                                     |------------------------------------->|
        | 7. Bootstrapped / Verified          |<-------------------------------------|
        |<------------------------------------|                                      |
```

---

## 3. Cryptographic Operation Digest Binding

To prevent **assertion substitution attacks** (where an attacker obtains a signature for a benign action and replays it against a root establishment action), the server binds the challenge to a deterministic SHA-256 digest of the operation parameters:

```python
op_digest = compute_canonical_operation_digest(
    action="COMPLETE_ROOT_BOOTSTRAP",
    params={
        "org_id": org_id,
        "nonce": nonce,
        "token_hash": token_hash,
        "root_public_key": root_public_key,
    }
)
```

The server refuses to consume the challenge or accept the assertion if the submitted request parameters do not yield the identical digest.

---

## 4. Multi-Device (Synced) vs. Hardware-Bound Passkeys

WhitePact explicitly models credential properties from the WebAuthn authenticator data flags:
- **`backup_eligible` (BE):** Indicates the credential can be synced across devices via cloud keychains (e.g., Apple iCloud Keychain, Google Password Manager).
- **`backup_state` (BS):** Indicates whether the credential is currently synced.
- **Hardware-Bound Security Keys (e.g., YubiKey):** Have `backup_eligible == 0`.

WhitePact does not claim that all passkeys are hardware-bound, but ensures all passkeys are **phishing-resistant** due to strict RP ID and origin binding enforced by the browser and cryptographic hardware enclave.

---

## 5. Security Invariants & Denial Guarantees

| Attack Vector | Defense Mechanism | Error Code |
|---|---|---|
| Challenge Replay | Atomic single-use `consumed_at` timestamp check within transaction | `WEBAUTHN_CHALLENGE_REPLAY` |
| Challenge Expiration | Strict 300-second TTL enforcement against server clock | `WEBAUTHN_CHALLENGE_EXPIRED` |
| Operation Substitution | SHA-256 parameter digest verification before signature validation | `WEBAUTHN_ASSERTION_INVALID` |
| Cross-Tenant Phishing | Strict tenant isolation: challenge hash queried with `org_id` and `user_id` | `WEBAUTHN_ASSERTION_INVALID` |
| Phishing / Relaying | Authenticator binds signature to exact browser origin and RP ID hash | `WEBAUTHN_ASSERTION_INVALID` |
| User Presence Bypass | Rejection if `FLAG_UP` (0x01) is missing from authenticator data | `WEBAUTHN_ASSERTION_INVALID` |
| User Verification Bypass | Rejection if `FLAG_UV` (0x04) is missing from authenticator data | `WEBAUTHN_ASSERTION_INVALID` |
| Authenticator Cloning | Sign counter strictly checked for monotonic advancement (if non-zero) | `WEBAUTHN_ASSERTION_INVALID` |
