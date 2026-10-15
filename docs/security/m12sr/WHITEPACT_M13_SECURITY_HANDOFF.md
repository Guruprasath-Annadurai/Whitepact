# WHITEPACT — MILESTONE 13 SECURITY HANDOFF SPECIFICATION
## UNIFIED INTEGRATION, CROSS-TEAM COLLABORATION & INDEPENDENT QUALIFICATION

- **Author:** Antigravity (Principal Security Architect)
- **Recipient:** Codex (Lead Product Architect), GPT-6 (WhitePact CTO / Technical Coordinator)
- **Source Security Branch:** `security/whitepact-m12s-customer-authority`
- **Candidate Commit SHA:** `0daa57aac92c97765eb8680a705e40534760bbf5`
- **Candidate Tree SHA:** `3f8dac4f6f724316289bcde7a9ab2324180efa66`
- **Milestone Scope:** Transition from M12-SR to M13 (Unified Production Qualification)

---

## 1. REPOSITORY & MERGE INTEGRATION PROTOCOL

### 1.1. Branch & Commit Hierarchy
- **Baseline Foundation:** Commit `0daa57aa` integrates:
  1. All historical M10-R security baselines (`7514a23a`).
  2. Codex published M12 product integration (`1a116b95`).
  3. Codex local successor commit `9bc83a12` (duplicate JSON key rejection).
  4. Complete customer root authority bootstrap lifecycle and adversarial test coverage.
- **Strict Release Gate:** **NO-GO FOR PRODUCTION DEPLOYMENT OR MERGE TO `main`**.
  - Merging into `main`, activating production billing, provisioning cloud infrastructure, or publishing packages remains **STRICTLY PROHIBITED** until M13 independent qualification and Founder Sign-off (Gate S12) are completed.

### 1.2. Division of Engineering Responsibilities
| Domain | Primary Owner | Secondary Reviewer |
| :--- | :--- | :--- |
| **Root-of-Trust & Trust Fabric** | Antigravity | Codex / GPT-6 |
| **Consent Proofs & Governance Root Lifecycle** | Antigravity | Codex |
| **Revocation & Execution Grants** | Antigravity | Codex |
| **Network Egress, Socket Guard & Containment** | Antigravity | Infra Lead |
| **Cryptographic Signing & Audit Evidence** | Antigravity | Compliance Lead |
| **Dashboard UI, Workflows & Settings Frontend** | Codex | Antigravity (CSRF/Auth only) |
| **Client SDKs (Python, TypeScript)** | Codex | Antigravity (Contract conformance) |
| **Developer Documentation & Quickstarts** | Codex | Antigravity |

---

## 2. M13 PREPARATION & CROSS-TEAM VERIFICATION CHECKLIST

Prior to initiating M13 unified qualification runs, the integration team must verify:

- [ ] **1. Exact Tree Conformance:** Ensure the unified integration branch contains commit `0daa57aa` or its direct linear descendant.
- [ ] **2. Customer Authority REST API Contract:** Confirm frontend and SDK clients consume the exact frozen routes defined in `docs/security/m12sr/WHITEPACT_CUSTOMER_AUTHORITY_API_CONTRACT.md`.
- [ ] **3. Dual-Cookie CSRF Headers:** Ensure dashboard frontend submits `X-WP-CSRF` matching `wp_csrf` cookie on all POST/PUT/DELETE requests.
- [ ] **4. MCP `isError=True` Handling:** Ensure client MCP wrappers parse `isError=True` payloads as denials rather than tool responses.
- [ ] **5. Unverified Static Key Deprecation:** Migrate all integration test fixtures from `RAI_API_KEYS` to `EnterpriseIAM.issue_api_key()`.
- [ ] **6. Audit Log Disclaimer Compliance:** Verify no user-facing UI or documentation claims "Merkle tree proofs"; verify usage of "hash-linked witness logs".
- [ ] **7. Founder Sign-Off (Gate S12):** Confirm founder selection of Decision A (WebAuthn) and Decision B (Quorum Revocation) in `docs/security/m12sr/WHITEPACT_FOUNDER_SECURITY_DECISIONS.md`.

---

## 3. UNIFIED QUALIFICATION COMMAND SET

The unifying team can execute the unified qualification harness with the following command:

```bash
# 1. Customer Authority & Trust Fabric Lifecycle Suite (9 tests)
uv run pytest tests/test_customer_root_authority_bootstrap.py -o addopts="" -v

# 2. Multi-Agent Concurrency & Revocation Suite (25 tests)
uv run pytest tests/test_m10r_concurrent_delegation.py tests/test_m10r_grant_epoch_invalidation.py tests/test_m10_multi_agent_delegation.py -o addopts="" -v

# 3. Controlled Egress & Execution Enforcement Suite (30 tests)
uv run pytest tests/test_m10r_real_socket_egress.py tests/test_m10r_consequential_enforcement.py tests/test_m10r_executors_egress.py -o addopts="" -v

# 4. Enterprise Identity, Revocation Outage & Approval Suite (34 tests)
uv run pytest tests/test_p0_tenant_admission.py tests/test_p0_revocation_outage.py tests/test_p0_approval_resume_adversarial.py -o addopts="" -v

# 5. MCP Protocol & Feature Registry Suite (55 tests)
uv run pytest tests/test_mcp_wave1_compatibility.py tests/test_m12_feature_registry.py -o addopts="" -v
```

---

## 4. CONCLUSION

Milestone M12-SR is officially concluded. The security foundation is solid, completely reconciled, and primed for unified Milestone M13 qualification.
