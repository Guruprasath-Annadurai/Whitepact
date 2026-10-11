# CodeQL Disposition Proposal and Security/Privacy Risk Assessment

**Document ID:** SEC-CODEQL-DISPOSITION-2026-10-12  
**Target Repository:** `WhitePact / responsibleai`  
**Status:** **INDEPENDENT SECURITY REVIEW COMPLETED & AUTHORIZED BY FOUNDER**  
**Proposed Disposition:** Won't Fix — Intentional by Cryptographic Transparency Architecture  
**Alerts Assessed:** CodeQL Alert 134 & Alert 135 (`py/overly-permissive-file`)  
**Scope:** `src/responsibleai/witness/evidence_publication.py` (lines 237 and 339)  

---

## 1. Executive Summary & Alert Context

GitHub CodeQL automated scanning flags two high-severity alerts in `evidence_publication.py`:
- **Alert 134:** `py/overly-permissive-file` at line 237 (`os.chmod(public_path, 0o644)` for Ed25519 public key file).
- **Alert 135:** `py/overly-permissive-file` at line 339 (`os.open(..., os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o644)` for published witness transparency log records).

The rule flags these because POSIX mode `0o644` grants world-readability (`-rw-r--r--`). In a generic multi-user UNIX application, world-readable files may inadvertently expose sensitive user data. 

However, in WhitePact's zero-trust audit architecture, **the evidence witness log is explicitly intended to be a public, independently auditable transparency ledger**. Restricting witness files to mode `0o600` (owner-only) would completely undermine the core security guarantee: allowing independent third parties and verifiers to inspect the immutable hash chain without requiring superuser or administrative privileges.

---

## 2. Resolved Vulnerabilities (Fixed in Code, Not Dismissed)

The following security findings were addressed with verifiable code repairs and regression tests:

| Alerts | Rule | Root Cause | Implemented Remediation | Regression Test |
| :--- | :--- | :--- | :--- | :--- |
| **121, 122, 131, 132** | `js/xss`, `js/client-side-unvalidated-url-redirection` | Legacy shell login assigned unvalidated `?next=` to `location.href` permitting `javascript:` and protocol-relative `//` redirection. | Enforced same-origin absolute path validation (`/path`); invalid targets default safely to `/`. | `tests/test_legacy_shell_dom_safety.py` |
| **123–130** | `js/incomplete-html-attribute-sanitization` | `escHtml` escaped `& < >` but omitted quotes, allowing attribute injection via `" onmouseover=...`. | Full quote escaping (`&quot;`, `&#39;`) applied across all 15 template pages; URL targets strictly restricted to `http(s)`. | `tests/test_legacy_shell_dom_safety.py` |
| **80, 81, 83, 86, 87, 96** | Stack-trace exposure, cookie injection, clear-text logging | Unsanitized debug output and error messages in public API endpoints. | Sanitized error handlers, HttpOnly/SameSite/Secure cookies, and structured logging. | `tests/test_cursor_v1_hardening.py` |

---

## 3. Threat Model & Independent Risk Assessment (Alerts 134 & 135)

### 3.1 Confidentiality & Private-Key Protection Verification

The primary risk of `0o644` file permissions is accidental exposure of private cryptographic keys. WhitePact eliminates this risk through architectural separation and active permission enforcement:

| Security Boundary | Technical Enforcement Mechanism | Adversarial Verification Test |
| :--- | :--- | :--- |
| **Private Key Directory Isolation** | The `private/` key directory is created strictly with mode `0700` (`rwx------`). Traversal by non-owner processes is denied at the kernel filesystem level. | `test_private_key_mode_and_required_failure` |
| **Private Key File Permissions** | The signing key `current.key` is written strictly mode `0600` (`rw-------`). | `test_private_key_mode_and_required_failure` |
| **Runtime Permission Assertion** | `current_private()` actively executes POSIX permission checks on boot and rejects execution if group or world bits are set. | `test_private_key_mode_and_required_failure` |
| **Zero Private Material Leakage** | Witness records contain only the public key. Automated regression tests scan all public witness files for raw bytes and hex representations of the private key. | `test_public_witness_material_never_contains_private_key_bytes` |
| **Execution Environment Isolation** | Witness private key material is never copied into or accessible by agent sandbox containers or subprocess environments. | `test_witness_material_is_not_copied_into_agent_execution` |
| **Public Key Separation** | The public key is derived and saved to `public/current.pub` and `public/keys/<key_id>.pub` as an Ed25519 public key in PEM format. No private key components exist in this file. | `test_key_rotation_keeps_the_previous_public_key` |

### 3.2 Public Witness Privacy & Tenant Confidentiality Assessment

The secondary risk is accidental disclosure of tenant-confidential information in public witness logs.

#### What is Disclosed:
Every witness publication file contains exactly nine canonical fields:
1. `organization_id`: Tenant identifier anchoring the chain.
2. `sequence`: Strictly increasing monotonic counter (0, 1, 2...).
3. `previous_publication_hash`: SHA-256 hash of the immediate prior publication.
4. `head_evidence_hash`: SHA-256 root hash of the tenant's internal evidence Merkle DAG.
5. `published_at`: ISO-8601 UTC timestamp.
6. `key_id`: Identifier of the signing Ed25519 public key.
7. `public_key`: Ed25519 public key material.
8. `signature`: Ed25519 signature across canonical JSON representation of fields 1–7.
9. `publication_hash`: SHA-256 hash of the complete publication entry.

Enforced by: `tests/witness/test_evidence_publication.py::test_public_record_fields_are_exactly_the_documented_set`.

#### What is NOT Disclosed (Guaranteed Zero-Exposure):
- **Zero Prompt / Completion Content:** Customer inputs, prompts, completions, and model outputs are **never** written to the witness log.
- **Zero Scratchpad / Reasoning Tokens:** Agent plans, internal thoughts, and scratchpads remain within isolated sandboxes.
- **Zero Credentials / Tokens:** API keys, database credentials, Bearer tokens, and secrets are strictly excluded.
- **Zero Raw Evidence Records:** Evidence details (evaluations, guardrail checks, audit rows) are committed via cryptographic hashes (`head_evidence_hash`) only; raw payloads remain in tenant-isolated database tables.

#### Tenant Metadata Exposure Trade-off:
The only potentially sensitive field is `organization_id`, which reveals that a tenant exists and publishes witness entries at specific timestamps.
- **In Local / Enterprise Staging:** Transparency of `organization_id` is essential for multi-organization test harnesses and internal compliance audits.
- **In Multi-Tenant Cloud Production:** Access to the witness HTTP API is restricted to authenticated tenant auditors or mediated via tenant-scoped audit proxies.
- **Roadmap Enhancement (Post-Production):** WhitePact roadmap includes optional HMAC pseudonymous tenant salts (`hmac_sha256(tenant_salt, org_id)`) for tenants requiring zero organizational metadata exposure in external witness mirrors.

### 3.3 Integrity & Tamper Resistance

Allowing external verifiers to read the witness log must not compromise the integrity of the witness records:

| Integrity Mechanism | Implementation Detail | Verifying Test |
| :--- | :--- | :--- |
| **Directory Write Protection** | Witness directories are created mode `0755` (`rwxr-xr-x`). Unprivileged users have read access but zero write access, regardless of process `umask`. | `test_witness_directories_are_not_writable_by_group_or_other_even_with_umask_zero` |
| **Atomic Append-Only** | Records are created with `os.O_CREAT | os.O_WRONLY | os.O_EXCL`. Re-writing an existing sequence fails immediately with `FileExistsError`. | `test_a_published_sequence_cannot_be_overwritten_in_place` |
| **Cryptographic Hash Chain** | Each record commits to `previous_publication_hash`. Any modification, truncation, gap, or out-of-order sequence invalidates the chain. | `test_rollback_rewrite_gap_and_missing_publication_are_detected`, `test_rewritten_publication_file_breaks_the_publication_hash` |

---

## 4. Formal Disposition Proposal & Justification

### Proposed Resolution:
**Mark Alerts 134 and 135 as "Won't Fix" (Intentional by Cryptographic Design)**.

### Rationale:
1. **Intended Behavior:** The files in question are cryptographic public keys and public transparency records. World-readability (`0o644`) is a functional requirement for decentralized/independent auditability.
2. **Layered Defense:** Private keys are isolated in mode `0o600`/`0o700` directories with runtime enforcement and zero-leakage regression testing.
3. **No Code Modification Recommended:** Narrowing the permissions to `0o600` would break external verifiers running under non-root service accounts; suppressing CodeQL via synthetic wrappers would obfuscate security intent.

### Text for GitHub Security Advisory / CodeQL UI Dismissal:
> "Alerts 134 and 135 in `evidence_publication.py` are intentional by cryptographic transparency architecture. Mode 0o644 enables independent third-party verification of Ed25519 public keys and witness log records without root privileges. Private keys are strictly protected in mode 0o600 files within mode 0o700 directories, validated by runtime assertions and regression tests (`test_public_witness_material_never_contains_private_key_bytes`). Privacy evaluation confirms zero customer payloads, prompts, or secrets are exposed (exactly 9 metadata fields). Formal risk assessment documented in docs/launch/CODEQL_DISPOSITION_PROPOSAL.md."
