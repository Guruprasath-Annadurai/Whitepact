# Technical evidence index (repository)

Evidence class prefixes match `compliance/CAIQ_EVIDENCE_BOUNDARY.md`.

| Domain | Mechanism | Primary paths | Tests / CI |
|--------|-----------|---------------|------------|
| Identity / MFA / WebAuthn | Layer 2 providers, TOTP, WebAuthn | `src/responsibleai/enterprise/security/`, `tests/test_mfa.py`, `tests/test_step_up_authentication.py` | `.github/workflows/ci.yml` |
| RBAC / tenant isolation | Org-scoped repositories | `src/responsibleai/`, `tests/test_tenant_isolation.py`, `tests/test_rbac.py` | CI |
| Authority / human oversight | Authority kernel, approvals | `src/responsibleai/runtime/authority_kernel.py`, `tests/test_workflow_authority.py` | CI |
| Audit logging | Tamper-evident hash chain | Audit writers in `dashboard/`, `tests/test_*audit*` | CI |
| Field encryption | Fernet / MultiFernet | `src/responsibleai/db/encryption.py`, `scripts/rotate_field_encryption_key.py` | Production validator in `dashboard/config.py` |
| MCP OAuth | Hosted transport security | `src/responsibleai/mcp/`, `tests/test_mcp_oauth*.py` | CI |
| Supply chain | Bandit, pip-audit, gitleaks, SBOM | `.github/workflows/security-scan.yml`, `release-evidence/*/supply-chain/` | Weekly + release |
| Data governance | Classification inventory | `src/responsibleai/data_governance/`, `tests/test_data_inventory` | CI |
| Egress / SSRF | Public-only fetch | `src/responsibleai/net/egress.py`, global directory tests | CI |
| Billing (production) | Paddle | `src/responsibleai/billing/paddle_service.py` | `tests/test_web_paddle_billing_routes.py` |

Re-audit procedure for each prior YES:

1. Locate control in ledger (post OA-001).  
2. Map to row in this index.  
3. Run cited tests.  
4. Downgrade to NO if evidence is documentation-only or optional-not-enforced.
