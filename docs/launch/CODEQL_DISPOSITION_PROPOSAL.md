# CodeQL Disposition Proposal and Security/Privacy Risk Assessment

**Document ID:** SEC-CODEQL-DISPOSITION-2026-10-12  
**Target Repository:** `WhitePact / responsibleai`  
**Status:** **PROPOSED — AWAITING INDEPENDENT SECURITY AND FOUNDER RISK ACCEPTANCE**  
**Proposed Disposition:** Under Independent Evaluation (Option A: Justified Won't Fix vs Option B: Hardened Local 0o600 with HTTP Gateway)  
**Alerts Assessed:** CodeQL Alert 134 & Alert 135 (`py/overly-permissive-file`)  
**Scope:** `src/responsibleai/witness/evidence_publication.py` (lines 237 and 339)  

---

## 1. Executive Summary & Alert Context

GitHub CodeQL automated scanning flags two high-severity alerts in `evidence_publication.py`:
- **Alert 134:** `py/overly-permissive-file` at line 237 (`os.chmod(public_path, 0o644)` for Ed25519 public key file).
- **Alert 135:** `py/overly-permissive-file` at line 339 (`os.open(..., os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o644)` for published witness transparency log records).

The rule flags these because POSIX mode `0o644` grants world-readability (`-rw-r--r--`). In a generic multi-user UNIX application, world-readable files may inadvertently expose sensitive user data. 

This document provides the formal threat model, privacy analysis, adversarial test evidence, and architectural options for independent reviewer and founder evaluation. **No alerts have been dismissed in the GitHub repository or CodeQL dashboard.**

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

The primary security risk of file permission misconfiguration is exposure of private cryptographic keys. WhitePact prevents private-key exposure through multiple defense-in-depth layers:

| Security Boundary | Technical Enforcement Mechanism | Adversarial Verification Test |
| :--- | :--- | :--- |
| **Private Key Directory Isolation** | The `private/` key directory is created strictly with mode `0700` (`rwx------`). Directory traversal by non-owner processes is denied at the kernel filesystem level. | `test_private_key_mode_and_required_failure` |
| **Private Key File Permissions** | The signing key `current.key` is written strictly mode `0600` (`rw-------`). | `test_private_key_mode_and_required_failure` |
| **Runtime Permission Assertion** | `current_private()` actively executes POSIX permission checks on boot and rejects execution if group or world bits are set. | `test_private_key_mode_and_required_failure` |
| **Zero Private Material Leakage** | Witness records contain only the public key. Automated regression tests scan all public witness files for raw bytes and hex representations of the private key. | `test_public_witness_material_never_contains_private_key_bytes` |
| **Execution Environment Isolation** | Witness private key material is never copied into or accessible by agent sandbox containers or subprocess environments. | `test_witness_material_is_not_copied_into_agent_execution` |
| **Public Key Separation** | The public key is derived and saved to `public/current.pub` and `public/keys/<key_id>.pub` as an Ed25519 public key in PEM format. No private key components exist in this file. | `test_key_rotation_keeps_the_previous_public_key` |

### 3.2 Public Witness Privacy & Tenant Confidentiality Assessment

The secondary risk is accidental disclosure of tenant-confidential information in public witness logs.

#### What is Disclosed:
Every witness publication file contains exactly nine canonical metadata fields:
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

### 3.3 Architectural Separation: Local Filesystem vs Remote Authenticated Access

An independent evaluation must distinguish between local filesystem access and remote network access:

1. **Local Filesystem Access (Current Implementation):**
   - Mode `0o644` allows other local UNIX user accounts on the same operating system to read `public/` records directly.
   - In containerized deployments (Docker/Kubernetes) where each container runs in an isolated filesystem namespace with a single service user, local world-readability does not expose data to unauthorized human users.
   - However, on shared multi-user developer workstations or shared bastion hosts, `0o644` permits other local users to inspect `organization_id` and publication frequency.

2. **Remote Access Boundary (Network Layer):**
   - External independent verifiers and compliance auditors do not access the local filesystem directly; they query the HTTP API (`/api/witness/publications/{org_id}`).
   - The HTTP gateway can authenticate verifiers (e.g., via auditor API keys or client certificates) and serve the exact same cryptographic evidence records over TLS.

### 3.4 Architectural Options for Founder and Reviewer Determination

- **Option A (Cryptographic Transparency Justification):**
  - Retain mode `0o644` for public witness records and public keys.
  - Document that world-readability is an intentional transparency feature for local audit daemons and verifiers.
  - Formally record founder and reviewer risk acceptance in CodeQL triage.

- **Option B (Hardened Local Permissions with HTTP-Mediated Verification):**
  - Change local file creation in `evidence_publication.py` from `0o644` to `0o600` (or `0o640` with a dedicated auditor group).
  - External verifiers obtain witness records exclusively via the HTTP API, which reads the `0o600` files under the application's service account and streams them to the verifier.
  - This completely resolves CodeQL Alerts 134 & 135 without modifying cryptographic data structures or breaking third-party verifiers.

---

## 4. Current Disposition Status

- **Status:** **PROPOSED — AWAITING INDEPENDENT SECURITY AND FOUNDER RISK ACCEPTANCE**.
- **Action Taken:** Alerts 134 & 135 remain **active and un-dismissed** pending founder and independent reviewer decision between Option A and Option B.
