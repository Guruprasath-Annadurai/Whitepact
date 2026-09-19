# WhitePact Enterprise SaaS Layer 2 — Identity Security Fortress

This document describes backend authentication trust. It is not a marketing claim
and does not describe the system as unhackable.

## Trust model

Verified Identity → Strong Authentication → Session Trust → Membership → RBAC
→ Step-Up → Credential Eligibility → WhitePact Governance → Execution Authority

These answers are distinct:

- Authentication: possession/control of a factor
- Identity verification: who the human is (`IDENTITY_VERIFIED`)
- Organization verification: which company this is
- Membership: whether the human belongs to that organization
- RBAC: administrative functions
- Governance: whether a consequential action may occur

`AUTHENTICATED != IDENTITY_VERIFIED`
`MFA_COMPLETE != IDENTITY_VERIFIED`
`GOOGLE_LOGIN != COMPANY_VERIFIED`
`SSO_SUCCESS != API_KEY_ELIGIBLE`
`OWNER != EXECUTION_AUTHORIZED`

Phone verification is `PHONE_VERIFIED` only. It is never strong authentication.

## Provider identity

Canonical provider identity is the signed subject (`sub`), plus tenant where
the provider supplies one (`hd` for Google Workspace, `tid` for Entra). Email
is a display hint. Email suffix matching never grants company membership.

Personal Google/Microsoft accounts authenticate an individual workspace unless
an administrator invites the human into a verified organization.

Google Workspace and Entra bindings are explicit organization records. Default
provisioning is invite-only. JIT requires organization opt-in and exact tenant
or hosted-domain match.

## Sessions

Session secrets are random, stored as SHA-256 hashes, rotated after
authentication, and revoked on password reset, identity suspension, membership
revocation, org suspension, recovery, and logout-all. Stolen sessions cannot
perform listed sensitive actions without a fresh action-bound step-up grant.

Device fields are risk context, not identity proof.

## Assurance and step-up

Assurance levels are ranked. Passkey UV and enterprise SSO (when the
organization policy says the IdP satisfies phishing resistance) outrank TOTP.
Google/Microsoft OIDC is not automatically phishing-resistant.

Step-up grants are hashed, short-lived, single-use, and bound to user, session,
and action.

## Recovery

Recovery is a privileged ceremony with an explicit state machine. Hashed
one-time codes and hashed short-lived tokens. OWNER/SECURITY_ADMIN recovery
cannot complete from a mailbox alone. Successful recovery revokes sessions.

## Break-glass

Break-glass identities are pre-configured, IDENTITY_VERIFIED, phishing-resistant,
audited, and cannot mint ExecutionAuthorization or bypass verified-principal
API-key issuance. There is no support master password.

## Fail-closed

JWKS refresh failure, signature failure, replay-repository failure, and
session-repository failure deny. Redis is never authentication authority.

## Production

`PRODUCTION_GATE_B_OPEN = False`. `PHASE7A_DISPATCHER_ENABLED` defaults false.
Layer 2 does not implement WSAF.
