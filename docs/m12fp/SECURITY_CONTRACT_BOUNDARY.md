# M12-FP customer authority preparation

WhitePact — AI Agents. Actions Under Authority.

## Ownership and integration boundary

Codex owns only `web/src/features/authority/`, its tests, this document and
M12-FP evidence reports. Antigravity owns root assurance, WebAuthn verification,
recovery quorum, containment, authority repositories and migrations. This branch
starts at M12-P `3592cfeaec946a38af20ca16ad38a54fb85c9454`; no security branch
is merged. PRs #204 and #205 are preserved.

The preparation component is not imported by production navigation. Its local
states are presentation vocabulary, **not an invented backend response schema**.
There is no mutation adapter or frontend authority algorithm. Disabled buttons
are an honest availability indication, never a security boundary.

## Identity, consent and authority

Signup and passkey enrollment authenticate identity; neither grants execution
authority. Root setup must show server-verified owner eligibility, exact purpose,
scope, action types and targets before explicit confirmation. Merely viewing a
page is not consent. A browser authenticator response must be verified by the
server and bound to the privileged operation before any root change is permitted.
No new assurance level is asserted by this implementation.

## Passkeys

`requestPasskey` passes reviewed native server options to `navigator.credentials`
and returns only the native response. It neither constructs challenges nor sends
requests, retries, installs sessions, serializes credentials, logs diagnostics or
writes browser storage. No production caller exists. The browser test constructs
explicit fixture options only, with a Chromium virtual authenticator; this is not
real server acceptance or a hardware authenticator qualification.

Cancellation and expiry can share `NotAllowedError`; the UI must not distinguish
them without authoritative evidence. Unsupported/insecure browsers cannot proceed.
Lost or revoked credentials require the reviewed recovery process, not a bypass.
Do not paste secrets into support tickets. Never resume a privileged operation
automatically from a return URL or successful browser prompt.

## Containment versus recovery

Containment restricts the documented authority boundary. It does not by itself
prove an already-running external effect stopped. Pending, UNKNOWN and unresolved
executions remain visible until canonical server status and incident evidence
resolve them. Recovery changes root authority and requires server-enforced quorum,
distinct eligible voters, expiry/conflict checks and re-authentication. The UI must
not derive approval from a vote count or silently expand consent.

After a lost mutation response, do not retry. Inspect a reviewed operation-specific
status endpoint and evidence. Current aggregate root status is not proof of a
particular ceremony result or of physical containment.

## Contracts still required from M12-FS

Reviewed at security reference `97657ece23229c16c626ceb5f6162c143c924a3b`:

- Native enrollment options and browser-cookie-compatible completion. Existing
  `enterprise/security/service.py:begin_webauthn` lacks full creation options;
  `security/router.py:passkey_auth_finish` returns a JSON session token.
- A unified reviewed browser CSRF contract: identity security `_session` accepts
  `x-whitepact-csrf`/`x-csrf-token`; authority `_web_actor` uses `X-WP-CSRF`.
- Operation-bound root step-up. `authority/service.py:CustomerAuthorityService`
  bootstrap verification-status checks are not WebAuthn step-up proof.
- Exact ceremony status, duplicate/replay and uncertain-result reconciliation.
- Emergency containment scope, pending/completion/unresolved status and evidence.
- Root recovery initiation, votes, authoritative quorum progress, expiry, conflict,
  suspension, stale request invalidation, completion and audit contracts.
- Accepted application/agent lifecycle contracts before enabling mutations. The
  existing read-only inventory preparation remains unchanged and inactive.

The M12-SR document and implementation also disagree on `/delegate` versus
`/delegations`, `has_canonical_root` versus `has_active_authority`, and several
status field names. Consume reviewed implementation contracts, not prose guesses.

## Test commands

Run `npm --prefix web ci --ignore-scripts`, `npm --prefix web test`,
`npm --prefix web run lint`, and `npm --prefix web run build`.
For the isolated browser fixture, install root locked dependencies, start local
Vite with `npm --prefix web run dev -- --host 127.0.0.1`, then run
`M12FP_PREVIEW_ORIGIN=http://localhost:4173 node tests/js/m12fp-authority-browser.e2e.mjs`.
Use the localhost hostname for WebAuthn RP validation rather than an IP RP ID.
This fixture exercises no backend, tenant enforcement or fresh-database workflow.

Production remains NO-GO. M13 requires separate authorization and independent
qualification. No push, deployment, package publication or cloud action is implied.
