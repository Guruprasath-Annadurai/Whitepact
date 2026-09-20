# WhitePact Enterprise SaaS Layer 2 — Identity Security Fortress

This document describes backend authentication trust. It is not a marketing claim
and does not describe the system as unhackable, zero-risk, or certified.

## Trust model

Verified Identity → Strong Authentication → Session Trust → Membership → RBAC
→ Step-Up → Credential Eligibility → WhitePact Governance → Execution Authority

These answers are distinct:

- Authentication: possession/control of a factor
- Identity verification: who the human is (`IDENTITY_VERIFIED`)
- Organization verification: which company this is
- Membership: whether the human belongs to that organization
- RBAC: administrative functions
- Step-up: a short-lived, action-bound grant after a fresh factor
- Governance: whether a consequential action may occur
- Execution authority: Phase 7A `ExecutionAuthorization` only (not Layer 2)

`AUTHENTICATED != IDENTITY_VERIFIED`
`MFA_COMPLETE != IDENTITY_VERIFIED`
`GOOGLE_LOGIN != COMPANY_VERIFIED`
`SSO_SUCCESS != API_KEY_ELIGIBLE`
`OWNER != EXECUTION_AUTHORIZED`

Phone verification is `PHONE_VERIFIED` only. It is never strong authentication.

Layer 2 does not mint `ExecutionAuthorization`, open Production Gate B, or
enable the Phase 7A dispatcher.

## Hosted Google / Microsoft login

Hosted production login is a **server-side confidential authorization-code +
PKCE** transaction:

- cryptographically random `state` and `nonce`
- 300-second single-use transaction in `identity_oauth_transactions` (PostgreSQL)
- server-side code exchange using the confidential client secret
- issuer, audience, signature, and nonce validation
- authorization-code and state replay rejection
- callback redirect binding
- fail-closed on token/JWKS/provider errors

The browser cannot submit a raw `id_token` to
`/api/enterprise/identity-providers/{google,microsoft}/login` and complete
hosted authentication. A raw-token helper exists only on
`IdentitySecurityService` when `allow_raw_id_token=True` **and** the process is
not production. Implicit flow is not implemented.

Authorization codes, ID tokens, access tokens, refresh tokens, PKCE verifiers,
and client secrets are never logged.

## Provider identity

Canonical provider identity is the signed subject (`sub`), plus tenant where
the provider supplies one (`hd` for Google Workspace, `tid` for Entra). Email
is a display hint. Email suffix matching never grants company membership.

Provider names are normalized (`google`, `Google`, `google_oidc` → `GOOGLE`).

Personal Google/Microsoft accounts authenticate an individual workspace unless
an administrator invites the human into a verified organization.

Google Workspace and Entra bindings are explicit organization records. Default
provisioning is invite-only. JIT requires organization opt-in, a verified
organization, and an exact `hd` / `tid` match to the binding. Unknown
domains/tenants do not JIT into arbitrary organizations.

## Sessions

Session secrets are random, stored as SHA-256 hashes, rotated after
authentication, and revoked on password reset, identity suspension, membership
revocation, org suspension, recovery, and logout-all. Stolen sessions cannot
perform listed sensitive actions without a fresh action-bound step-up grant.

Device fields are risk context, not identity proof.

## Assurance and step-up

Assurance is derived from **authentication evidence**, not from an organization
checkbox.

| Evidence | Session level | Phishing-resistant |
| :--- | :--- | :--- |
| WebAuthn with UV | `PASSKEY_UV` | yes, when UV is verified |
| TOTP | `TOTP` (`PASSWORD_PLUS_TOTP`) | no |
| Hosted Google/Microsoft OIDC | `GOOGLE_OIDC` / `MICROSOFT_OIDC` | no |
| Enterprise SSO without reviewed `amr`/`acr` | `ENTERPRISE_SSO` | no (`ENTERPRISE_SSO_STANDARD`) |
| Enterprise SSO with signed `amr` in `{hwk,pop,sc,fpt}` or a reviewed hardware/smartcard ACR | `ENTERPRISE_SSO` | yes (`ENTERPRISE_SSO_PHISHING_RESISTANT`) |
| Generic `mfa` / REFEDS MFA / password AuthnContext | `ENTERPRISE_SSO` | no |
| Unknown evidence | lower safe level | no |

`ENTERPRISE_SSO_PHISHING_RESISTANT` is assigned only when signed provider
evidence maps to a reviewed method. An administrator checkbox is ignored.

Privileged actions that require a higher assurance fail closed.

Step-up grants are hashed, short-lived, single-use, and bound to user, session,
and action. Passkey enrollment consumes `ADD_PASSKEY` step-up and cannot be
the first strong factor from a password-only stolen session.

## Four-eyes

Privileged identity-security downgrades (including disabling required SSO) use
a maker-checker workflow in `identity_four_eyes_requests`:

`PENDING` → `APPROVED` → `CONSUMED` (or `DENIED` / `EXPIRED` / `REVOKED`)

The approver must be a different active human principal in the same
organization, with a privileged role and sufficient assurance. Self-approval,
cross-tenant approval, service accounts, replay, mutation after approval, and
expired tickets fail. Four-eyes is administrative dual control, not execution
authority.

## Recovery

Recovery uses hashed one-time codes and hashed short-lived tokens.
OWNER/SECURITY_ADMIN recovery cannot complete from mailbox ownership alone; a
recovery code is required. Successful recovery revokes sessions and unused
step-up grants. A recovered principal does not receive execution authority.

## WebAuthn

V1 verifies challenge, origin, RP ID, credential ID, user binding, user
presence, user verification (required), ES256 signature, and sign-count
advance. Counter updates are conditional (`sign_count < new`) so a stale
replica cannot overwrite a newer counter. **ES256 / P-256 only**: other COSE
algorithms are rejected. Authenticators that never increment the counter
(`0 → 0`) are accepted but provide weak clone detection.

## Abuse protection

Identity throttles use `identity_rate_counters` in the shared database. There
is no silent in-memory production fallback. Storage failure returns
`IDENTITY_PROTECTION_UNAVAILABLE` (fail closed) and does not grant more
privilege. Redis may assist other dashboard limits; it is not identity
authority. Client IP from spoofable headers is not the sole throttle key.

## Encrypted fields

Production/enterprise ciphertext uses envelope `wpenc:v1:` (historical Fernet
`gAAAA…` tokens remain decryptable). Authentication failure, unknown format,
and unknown keys **hard-fail**. Ciphertext is never returned as plaintext.

Explicit legacy plaintext is `wplegacy:v0:` and is permitted only when
`WHITEPACT_ALLOW_LEGACY_PLAINTEXT=1` in a **non-production** environment.
To migrate leftover plaintext: wrap with `wplegacy:v0:` in a maintenance
window, then re-encrypt under `wpenc:v1:` and drop the flag.

## Fail-closed

JWKS refresh failure, signature failure, replay-repository failure,
OAuth-transaction storage failure, rate-limit storage failure, and
session-repository failure deny. Redis is never authentication authority.

## Production preflight

Production startup fails closed when Layer 2 is enabled without:

- confidential OAuth client secrets (no placeholders)
- HTTPS WebAuthn origin and RP ID
- field encryption key
- refusal of raw `id_token` login and OIDC skip-verification

Optional features that are genuinely disabled do not fail the boot.

## Production

`PRODUCTION_GATE_B_OPEN = False`. `PHASE7A_DISPATCHER_ENABLED` defaults false.
Layer 2 does not implement WSAF.
