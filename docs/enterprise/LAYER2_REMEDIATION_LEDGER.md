# Layer 2 identity-security remediation ledger

Source and tests decide status. Documentation claims are not evidence.

## FINDING: Hosted Google/Microsoft accepted raw client `id_token`

REPRODUCED: YES  
ROOT CAUSE: `/api/enterprise/identity-providers/{google,microsoft}/login` treated a client-supplied JWT as the login artifact with no authorization-code exchange, PKCE, or durable transaction.  
FILES: `src/responsibleai/enterprise/security/router.py`, `service.py`, `oauth.py`, `oidc.py`  
SECURITY IMPACT: A leaked or foreign-client `id_token` with a matching nonce string could complete hosted login.  
REMEDIATION: Confidential authorization-code + PKCE; PostgreSQL `identity_oauth_transactions`; hosted login endpoints reject raw tokens; test-only `allow_raw_id_token` is production-forbidden.  
TESTS: `tests/test_enterprise_layer2_remediation.py` (`test_raw_hosted_id_token_rejected`, hosted OAuth success/replay/PKCE/nonce/redirect/JWKS).  
FINAL STATUS: CLOSED (source + tests)

## FINDING: OIDC transaction state was not durable

REPRODUCED: YES  
ROOT CAUSE: Layer 2 Google/Microsoft login had no server-side transaction row.  
FILES: `identity_oauth_transactions` (engine + migration 0057), `oauth.py`  
SECURITY IMPACT: No atomic consume, no replica-safe replay rejection, no redirect binding.  
REMEDIATION: Durable PENDING→CONSUMED rows; fail closed if storage is unavailable.  
TESTS: hosted OAuth tests; `test_postgres_oauth_state_and_rate_limit_and_four_eyes`.  
FINAL STATUS: CLOSED

## FINDING: Identity rate limiting was process-local

REPRODUCED: YES  
ROOT CAUSE: `IdentityRateLimiter` used an in-process dict. SSO/provider callbacks were unthrottled.  
FILES: `src/responsibleai/enterprise/security/rate_limit.py`, `identity_rate_counters`  
SECURITY IMPACT: Limits scaled with replica count; storage outage could have been designed to fail open.  
REMEDIATION: Shared SQL counters; storage errors raise `IDENTITY_PROTECTION_UNAVAILABLE`; no in-memory production fallback.  
TESTS: `test_distributed_rate_limit_shared_and_fail_closed`, PostgreSQL shared-counter test.  
FINAL STATUS: CLOSED

## FINDING: `cbor2` declared but not locked

REPRODUCED: YES (lockfile)  
ROOT CAUSE: `pyproject.toml` listed `cbor2` in `dashboard`/`dev`; `uv.lock` omitted it.  
FILES: `uv.lock`, `pyproject.toml`  
SECURITY IMPACT: Clean installs could fail WebAuthn COSE parse or silently miss the dependency.  
REMEDIATION: `uv lock` added `cbor2==6.1.4`. Clean venv: `python -m venv .venv && .venv/bin/pip install -e ".[dev,sso]"`.  
TESTS: `tests/webauthn_fakes.py` imports `cbor2`; WebAuthn tests execute the COSE path.  
FINAL STATUS: CLOSED

## FINDING: Phishing resistance from org policy / method name

REPRODUCED: YES  
ROOT CAUSE: `issue_session` marked all `ENTERPRISE_SSO` as phishing-resistant; `provider_is_phishing_resistant` trusted an org boolean.  
FILES: `assurance.py`, `policy.py`, `service.py`  
SECURITY IMPACT: Password IdP SSO could unlock break-glass / privilege gates.  
REMEDIATION: Evidence mapper (`amr`/`acr`/WebAuthn UV). Unknown and generic MFA map lower. Org checkbox ignored.  
TESTS: `test_assurance_evidence_not_org_policy`, `test_privileged_action_rejects_low_assurance`.  
FINAL STATUS: CLOSED

## FINDING: Dual control was a permanent deny

REPRODUCED: YES  
ROOT CAUSE: `dual_control_actions` unused; SSO required→optional always 403.  
FILES: `four_eyes.py`, `identity_four_eyes_requests`, `service.py` `configure_sso`  
SECURITY IMPACT: Operators could not complete a controlled maker-checker; message claimed dual control that did not exist.  
REMEDIATION: Layer 2 four-eyes state machine; consume required to disable required SSO.  
TESTS: `test_four_eyes_workflow`, `test_four_eyes_expiry_and_suspension`.  
FINAL STATUS: CLOSED

## FINDING: Production domain/org auto-trust via email suffix

REPRODUCED: NO (as auto-join). Residual: `JIT_OPT_IN` was stored but never executed.  
ROOT CAUSE: Login already required `provider_identities` + membership; email suffix did not grant org membership.  
FILES: `service.py` `_assert_membership_or_jit`  
SECURITY IMPACT: Claimed auto-trust not present. Dead JIT flag was an ops gap.  
REMEDIATION: JIT only with verified org + exact `hd`/`tid` binding; invite-only remains default.  
TESTS: existing `test_google_forged_issuer_audience_nonce_hd`; alias/email tests.  
FINAL STATUS: CLOSED (no auto-trust defect; JIT now explicit)

## FINDING: EncryptedString fail-open

REPRODUCED: YES  
ROOT CAUSE: Decrypt/`InvalidToken` returned the stored value as plaintext.  
FILES: `src/responsibleai/db/encryption.py`  
SECURITY IMPACT: Wrong key, corrupt ciphertext, or unknown format could surface ciphertext as if it were a secret.  
REMEDIATION: `wpenc:v1:` envelope; historical `gAAAA` Fernet decrypt-or-hard-fail; `wplegacy:v0:` only with non-production flag; never return ciphertext as plaintext.  
TESTS: `tests/test_field_encryption.py` fail-closed cases.  
FINAL STATUS: CLOSED

## FINDING: WebAuthn privileged enrollment / ES256 / counters

REPRODUCED: MIXED  
ROOT CAUSE: `finish_passkey_registration` did not consume step-up; ES256-only; counter `if previous and new <= previous` skipped stored `0`.  
FILES: `webauthn.py`, `service.py`  
SECURITY IMPACT: Password session could enroll a passkey without action-bound step-up.  
REMEDIATION: `require_step_up(ADD_PASSKEY)`; conditional counter update; ES256-only documented and unsupported algs rejected.  
TESTS: existing origin/RP/challenge tests; `test_password_session_cannot_enroll_passkey`; `test_unsupported_webauthn_algorithm_rejected`; PostgreSQL registration race.  
FINAL STATUS: CLOSED

## FINDING: Email as canonical provider key / alias collision

REPRODUCED: NO  
ROOT CAUSE: Unique key already `(provider, subject, tenant_id)`.  
REMEDIATION: Explicit `canonicalize_provider`.  
TESTS: `test_provider_alias_and_email_not_identity`, existing link-conflict test.  
FINAL STATUS: CLOSED (hardening only)

## FINDING: Privileged recovery ceremony incomplete

REPRODUCED: YES  
ROOT CAUSE: `RECOVERY_REVIEW` always denied before the recovery-code branch; `passkey_ok` boolean was a dangerous stub.  
FILES: `service.py` `consume_recovery_token`  
SECURITY IMPACT: Mailbox-only OWNER takeover blocked (good) but no completable stronger path; boolean could have been abused later.  
REMEDIATION: Privileged consume requires a one-time recovery code; boolean passkey shortcut rejected; sessions and step-up grants revoked.  
TESTS: `test_privileged_recovery_requires_recovery_code`; existing owner email-only block.  
FINAL STATUS: CLOSED

## FINDING: Production preflight gaps

REPRODUCED: PARTIAL  
ROOT CAUSE: Empty WebAuthn origin skipped HTTPS check; raw-token mode not refused; rate-limit topology not identity-authoritative.  
FILES: `preflight.py`  
REMEDIATION: Production requires encryption, HTTPS WebAuthn origin/RP ID, refuses raw id_token and skip-verification, rejects placeholder OAuth secrets.  
TESTS: `test_production_preflight_rejects_placeholders`, `test_production_preflight_requires_webauthn_and_rejects_raw_token`.  
FINAL STATUS: CLOSED

## FINDING: Layer 2 minting execution authority / Gate B

REPRODUCED: NO  
ROOT CAUSE: Layer 2 only reads `PRODUCTION_GATE_B_OPEN` as a deny guard.  
REMEDIATION: Regression test retained and extended.  
TESTS: `test_gate_b_closed_and_identity_cannot_mint_execution`.  
FINAL STATUS: CLOSED (invariant held)

## OUT-OF-SCOPE FINDING

- Dashboard SAML AuthnRequest correlation is durable (`dashboard_saml_transactions`); generic dashboard SSO is not Layer 2 hosted Google/MS.  
- Dashboard slowapi may still warn-only on multi-replica in-memory Redis; Layer 2 identity counters no longer use that path.  
- `uv.lock` refresh may have resolved other extras besides `cbor2`; review lock diff.  
- Historical Alembic head tests updated from `0056` to `0057` (required for a new linear migration).
- `identity_oauth_transactions`, `identity_rate_counters`, and `identity_four_eyes_requests` classified in the data inventory (PERSONAL/HIGH session, SENSITIVE_SECURITY, TENANT_OPERATIONAL respectively).  
