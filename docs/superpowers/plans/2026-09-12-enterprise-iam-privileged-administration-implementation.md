# WhitePact Enterprise Phase 4: Enterprise IAM, Privileged Access & Sovereign Recovery
## Superpowers Implementation Plan

**Document:** `docs/superpowers/plans/2026-09-12-enterprise-iam-privileged-administration-implementation.md`
**Status:** READY TO EXECUTE
**Target Branch:** `feature/enterprise-iam-phase4`
**Baseline SHA:** `53704a12269aea6eb467241a016c163d1e13e7df`

---

### Implementation Milestones & Task Breakdown

#### Milestone 1: Privileged Surface Guard & Canonical Chokepoint (4A)
- [ ] Create `src/responsibleai/iam/enums.py`:
  - `PrivilegeRiskTier` (`PRIVILEGED_STANDARD`, `PRIVILEGED_HIGH`, `PRIVILEGED_CRITICAL`)
  - `PrivilegedAction` (all actions mapped to their default tier)
  - `StepUpMethod` (`MFA_TOTP`, `OIDC_AUTH_TIME`, `WEBAUTHN`, `RECOVERY_CEREMONY`)
  - `JitGrantStatus`, `FourEyesStatus`, `BreakGlassStatus`
- [ ] Create `src/responsibleai/iam/errors.py`:
  - `PrivilegedAccessDeniedError`, `StepUpRequiredError`, `FourEyesRequiredError`, `BreakGlassExpiredError`, `SovereignRecoveryError`, `CrossTenantEscalationError`
- [ ] Create `src/responsibleai/iam/attribution.py`:
  - `PrivilegedAttributionEngine`: Hash-chained tamper-evident audit logger for privileged actions.
- [ ] Create `src/responsibleai/iam/guard.py`:
  - `authorize_privileged_operation` canonical chokepoint.
- [ ] Create tests:
  - `tests/test_privileged_surface_guard.py`
  - `tests/test_privileged_attribution.py`

#### Milestone 2: Step-Up Reauthentication & Nonce Binding (4B)
- [ ] Create `src/responsibleai/iam/step_up.py`:
  - `StepUpProof` dataclass (nonce, auth_time, method, signature/token).
  - `StepUpVerifier` verifying freshness (≤15m for HIGH, ≤5m for CRITICAL), nonce single-use consumption, action binding.
  - OIDC step-up verification checking `auth_time` claim and `acr`/`amr` factors.
- [ ] Create tests:
  - `tests/test_step_up_authentication.py`
  - `tests/test_step_up_adversarial.py` (replay, expiration, nonce manipulation, algorithm substitution)

#### Milestone 3: SCIM 2.0 & Session / API Key Lifecycle (4C)
- [ ] Create `src/responsibleai/iam/session.py`:
  - `SessionService`: Session creation, revocation by ID, revocation of all sessions for a principal, tenant epoch invalidation.
- [ ] Create `src/responsibleai/iam/api_key.py`:
  - `ApiKeyService`: API key rotation lineage, SHA-256 fingerprinting, zero plaintext key storage, revocation cascade.
- [ ] Create `src/responsibleai/iam/scim.py`:
  - RFC 7643/7644 schemas and services for `/scim/v2/ServiceProviderConfig`, `/scim/v2/Users`, `/scim/v2/Groups`.
  - Deprovisioning propagation hook: deactivating a user immediately revokes sessions, invalidates active JIT grants, and revokes assigned API keys.
  - Strict anti-root-escalation invariant: SCIM cannot create or elevate users to `OWNER`/`ROOT`.
- [ ] Create tests:
  - `tests/test_scim_users.py`, `tests/test_scim_groups.py`, `tests/test_scim_security.py`
  - `tests/test_session_revocation.py`, `tests/test_api_key_lifecycle.py`

#### Milestone 4: Just-In-Time (JIT) & Four-Eyes Dual Custody (4D)
- [ ] Create `src/responsibleai/iam/jit.py`:
  - `JitAccessService`: Request, approval, activation, and expiration of time-bounded grants. Automatic expiry enforcement.
- [ ] Create `src/responsibleai/iam/four_eyes.py`:
  - `FourEyesService`: Dual-custody workflow requiring independent approver principal (`approver != requester`), anti-self-approval, session independence check.
- [ ] Create tests:
  - `tests/test_jit_privileged_access.py`
  - `tests/test_four_eyes.py`

#### Milestone 5: Break-Glass Emergency Governance (4E)
- [ ] Create `src/responsibleai/iam/break_glass.py`:
  - `BreakGlassService`: Controlled emergency sessions requiring explicit incident identifier, strictly scoped capabilities (`RESTORE_IDP_CONFIGURATION`, `REVOKE_COMPROMISED_CREDENTIAL`, `EMERGENCY_DATA_EXPORT`), short TTL (≤60m), and mandatory Step-Up.
  - Zero permanent privilege invariant: emergency access self-terminates.
- [ ] Create tests:
  - `tests/test_break_glass.py`

#### Milestone 6: Sovereign Root Recovery & Sovereign Transfer (4F)
- [ ] Create `src/responsibleai/iam/recovery.py`:
  - `SovereignRecoveryService`: Guardian policy registration ($M$ Ed25519 public keys, threshold $N$), challenge generation, threshold signature aggregation, atomic root replacement, old root credential destruction, tenant epoch increment.
  - Zero WhitePact operator backdoor enforcement.
- [ ] Create `src/responsibleai/iam/transfer.py`:
  - `SovereignTransferService`: Voluntary root handover requiring current root step-up authentication and new root acceptance ceremony.
- [ ] Create tests:
  - `tests/test_root_recovery.py`
  - `tests/test_root_transfer.py`

#### Milestone 7: Database Migration `0044` & Real PostgreSQL Verification (4G)
- [ ] Update `src/responsibleai/db/engine.py` with the new IAM tables.
- [ ] Create Alembic migration `migrations/versions/0044_enterprise_iam_privileged_admin.py` with `down_revision = "0043"`.
- [ ] Create migration test `tests/test_phase4_migrations.py`:
  - Test upgrade to `0044`, downgrade to `0043`, re-upgrade to `0044`.
  - Test single head validation.
- [ ] Run on live PostgreSQL 17 database (`wp_phase3_test`).

#### Milestone 8: Adversarial Red-Team Matrix (50 Vectors) & Full Regression (4H)
- [ ] Create `tests/test_iam_adversarial_matrix.py` implementing all 50 required attack vectors.
- [ ] Run full repository regression suite (`pytest`). Target: 0 failed.
- [ ] Run static security checks (`ruff`, `mypy`, `license headers`, `git diff --check`, `gitleaks dir --verbose`, DCO commit log check).

#### Milestone 9: Final Evidence Closure Report (4I)
- [ ] Create `docs/security/PHASE4_ENTERPRISE_IAM_CLOSURE.md`.
- [ ] Format exact Section 71 final report output ending with `STOP.`.
