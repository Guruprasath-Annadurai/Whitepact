# WP-M13-POL-002 — controlling M13 engineering policy

Source: explicit user-provided founder security policy decision during M13-R.
Status: APPROVED FOR M13 ENGINEERING IMPLEMENTATION, not implementation acceptance.
Global production NO-GO. Security remediation owner: Antigravity.

An authenticated, explicitly authorized responder may use a current valid WebAuthn
assertion or a previously server-verified step-up authorization. Cached authorization
must bind the same principal, organization, session and exact canonical containment
operation digest; have short server-enforced expiry; be atomically consumed once;
and revalidate current responder authority and authenticator status. It cannot be
extended client-side, transferred across sessions, replayed or used for recovery or
authority expansion. Audit must record verified credential, decision, consumption
and resulting containment state. Login, a generic MFA flag, bearer token or browser
boolean is insufficient.

No WebAuthn-bypass interactive break-glass is approved at M13. Missing both valid
forms of step-up requires denial. Existing independently authorized automatic
restrictive controls may continue under their separate reviewed rules, never as an
implicit interactive administrator bypass. Future human break-glass needs separate
founder approval and adversarial qualification.

Restrictive emergency containment does not require recovery quorum. Root recovery,
transfer, restoration and expansion retain independent operation-bound quorum rules.
Authority restriction does not prove physical termination; failed/uncertain
termination must preserve restrictive enforcement and report UNRESOLVED.

Preserve the original missing-step-up test. Test termination failure with genuinely
server-verified cryptography, not mocked verification. Qualify direct assertions,
cached authorization one-shot consumption, expiry, replay, session/principal/tenant/
operation mismatch, credential/membership revocation, API-key-only requests,
concurrent use and server/database failure. P0-02 remains OPEN until independent
execution proves the corrected contract. No merge, deployment, cloud or M14 action.
