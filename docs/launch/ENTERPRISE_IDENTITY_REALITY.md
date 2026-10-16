# Enterprise Identity & IdP Federation Reality Disclosure

**Document ID:** DISC-ENTERPRISE-IDENTITY-2026-10-12  
**Target Candidate:** PR #185 (`review/whitepact-production-candidate`)  
**Status:** **AUTHORITATIVE TRUTHFULNESS DISCLOSURE (NO LIVE CERTIFIED IdP)**  
**Classification:** Product Reality & Engineering Boundary  

---

## 1. Truthful Status: Mocked / Hermetic Testing Only

WhitePact provides OIDC and SAML 2.0 authentication integration for enterprise tenants. However:

> [!IMPORTANT]
> **WhitePact does NOT have a live, third-party certified integration with Okta, Microsoft Entra ID (Azure AD), Ping Identity, or Google Workspace.**
>
> All enterprise single sign-on (SSO), SAML assertions, and OIDC token validation suites currently in the codebase are verified exclusively against **hermetic in-process test fixtures, cryptographic key mocks, and synthetic identity providers**.

No customer, investor, or evaluator should assume that a production SaaS federation agreement or certified marketplace integration currently exists with any third-party Identity Provider (IdP).

---

## 2. Technical Capabilities vs. Operating Reality

| Capability | Technical Implementation | Current Test Reality | Live Integration Status |
| :--- | :--- | :--- | :--- |
| **OIDC Token Validation** | `src/responsibleai/auth/oidc.py` (`OIDCProvider`) | Local JWKS mocks, synthetic RS256 token verification in `tests/test_oidc.py`. | **Not provisioned with live IdP tenant.** |
| **SAML 2.0 AuthnRequest & ACS** | `src/responsibleai/auth/saml.py`, `saml_transactions.py` | In-memory XML signing, mock X.509 cert validation, replay guard tests in `tests/test_saml.py`. | **Not federated with live Okta/Entra IdP.** |
| **Durable Replay Prevention** | `DurableSamlAuthnStore` backed by SQL engine | Verified with SQLite and PostgreSQL integration fixtures. | **Verified locally; no live multi-region IdP.** |
| **Privileged Surface IAM** | `src/responsibleai/iam/guard.py`, `step_up.py` | Single-use nonces, tiered step-up reauthentication tests in `tests/test_privileged_surface_guard.py`. | **Hermetic unit/integration tests only.** |
| **SCIM 2.0 Provisioning** | Standard models drafted in enterprise specs | Draft schemas in `docs/enterprise/LAYER2_IDENTITY_SECURITY.md`. | **Not implemented in runtime API routes.** |

---

## 3. Operating Constraints for Evaluators

1. In the zero-cash enterprise staging environment, enterprise SSO must be evaluated using either:
   - Self-hosted mock OIDC provider (e.g., local Keycloak or synthetic test IdP).
   - Local API key authentication (`Authorization: Bearer <key>`).
2. Live production SaaS federation requires dedicated enterprise IdP sandbox tenants, which have not been commissioned under the zero-cash development constraint (\$0.00).
3. Canonical reference: `docs/security/PHASE4_ENTERPRISE_IAM_CLOSURE.md` and `docs/enterprise/LAYER2_IDENTITY_SECURITY.md`.
