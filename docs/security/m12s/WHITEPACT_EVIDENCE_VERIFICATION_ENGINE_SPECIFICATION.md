# WHITEPACT — CRYPTOGRAPHIC EVIDENCE & VERIFICATION ENGINE SPECIFICATION

**Document ID:** WP-M12S-EVID-009  
**Classification:** CRYPTOGRAPHIC SPECIFICATION & AUDIT SCHEMAS  
**Audience:** Cryptographers, Compliance Auditors, Security Engineers  
**Modules:** `responsibleai.governance.evidence`, `responsibleai.governance.evidence_bundle`, `responsibleai.db.evidence_repository`  
**Status:** SPECIFIED & VERIFIED

---

## 1. PURPOSE & NON-REPUDIATION GUARANTEES

WhitePact produces immutable, mathematically verifiable audit trails for every consequential action evaluated or dispatched.

### Core Cryptographic Principles:
1. **Canonical JSON Serialization:** All hashes are computed over canonicalized UTF-8 JSON representations:
   - Keys sorted lexicographically (`sort_keys=True`).
   - Standard whitespace separators (`separators=(',', ':')`).
   - Strict `NaN` and `Infinity` rejection (`allow_nan=False`).
2. **SHA-256 Digest Chains:** Each evidence record references the hash of preceding governance artifacts (consent digest, root digest, decision digest).
3. **Detached Ed25519 Signatures:** Evidence bundles exported for external regulatory inspection carry detached Ed25519 signatures issued by the customer's root authority or the platform's signing notary.

---

## 2. CANONICAL RECORD SCHEMAS & DIGESTS

### 2.1 Canonical Root Authority Record Digest
$$\text{Digest} = \text{SHA-256}(\text{canonical\_json}(\text{root\_id}, \text{root\_type}, \text{subject\_id}, \text{org\_id}, \text{issuer}, \text{verification\_method}, \text{authority\_source}, \text{issued\_at}, \text{not\_before}, \text{expires\_at}, \text{evidence\_refs}, \text{jurisdiction}))$$

### 2.2 Canonical Consent Proof Digest
$$\text{Digest} = \text{SHA-256}(\text{canonical\_json}(\text{consent\_id}, \text{subject\_id}, \text{consenting\_root\_id}, \text{grantee\_id}, \text{scope\_description}, \text{purpose}, \text{consent\_method}, \text{allowed\_action\_types}, \text{allowed\_targets}, \text{evidence\_refs}, \text{consented\_at}, \text{not\_before}, \text{expires\_at}))$$

### 2.3 Evidence Record Schema
```json
{
  "evidence_id": "ev_uuid_here",
  "organization_id": "org_uuid_here",
  "action_id": "act_uuid_here",
  "action_type": "invoice:read",
  "target": "invoices/2026/001",
  "purpose": "invoice-reconciliation",
  "actor_id": "agent_a72d308c96d4",
  "root_authority_id": "root_uuid_here",
  "consent_id": "consent_uuid_here",
  "delegation_id": "del_uuid_here",
  "decision": "ALLOW",
  "policy_version": 4,
  "revocation_epoch": 1,
  "executed_at": "2026-10-15T10:33:05.123456+00:00",
  "action_digest": "sha256_action_hash...",
  "canonical_record_hash": "sha256_complete_record_hash..."
}
```

---

## 3. EVIDENCE BUNDLE & EXPORT VERIFICATION

For third-party regulatory compliance (SOC2 Type II, ISO 27001, HIPAA, EU AI Act), WhitePact packages governance trails into an `EvidenceBundle`:

```
+-------------------------------------------------------------+
|                      EvidenceBundle                         |
|                                                             |
|  +-------------------------------------------------------+  |
|  | Manifest (Bundle ID, Created At, Organization ID)     |  |
|  +-------------------------------------------------------+  |
|  | Root Authority Record + Ed25519 Public Key Certificate|  |
|  +-------------------------------------------------------+  |
|  | Customer Consent Proofs (Signed by Customer Root)     |  |
|  +-------------------------------------------------------+  |
|  | Full Delegation Chain (Root -> Intermediate -> Agent) |  |
|  +-------------------------------------------------------+  |
|  | Human Approval Record (Voters, Quorum, Signatures)    |  |
|  +-------------------------------------------------------+  |
|  | Execution Nonce Admission & Isolated Runtime Log      |  |
|  +-------------------------------------------------------+  |
|  | Merkle Root Hash over all constituent records          |  |
|  +-------------------------------------------------------+  |
|  | Detached Ed25519 Signature over Merkle Root           |  |
+-------------------------------------------------------------+
```

### Verification Algorithm:
1. Re-serialize each record using canonical JSON rules.
2. Recompute each record's SHA-256 digest and compare against the manifest.
3. Compute the Merkle tree over all digests and verify the Merkle root.
4. Verify the detached Ed25519 signature against the tenant's root public key.
5. If any byte was altered in transit, signature verification fails and flags tampering with exact leaf identification.
