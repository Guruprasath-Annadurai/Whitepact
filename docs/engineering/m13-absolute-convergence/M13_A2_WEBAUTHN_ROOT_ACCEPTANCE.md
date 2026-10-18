# M13 A2 WebAuthn/root acceptance

Tested source HEAD `7939341fd9d98d0f1fa39ce4421318dbc1dac33e`; tree `6bf30ee0d11c8137ec6a77844b1517de50d89edd`; parent `3be566129be44e00e92a07dd9449c957751eeb5d`. Candidate branch `codex/whitepact-m13-absolute-convergence`, [draft PR220](https://github.com/Guruprasath-Annadurai/Whitepact/pull/220). Production `src` subtree `bbd0e5f0b6a7dd02b388ab45d4dc5a7fed9036f1` is unchanged since296ad7ff. Final reports live on documentation-only branch `codex/whitepact-m13-absolute-evidence`. Historical receipts identify their own HEAD and do not substitute for final7939341f evidence.

Verdict: A2 enforced; mandatory independent root qualification PARTIAL/BLOCKED. Verified email plus recent server-verified WebAuthn UV, current active owner membership, consent and root proof-of-possession are required. This proves account/authenticator control, not legal identity. Reusable API-key IDENTITY_VERIFIED requirements are unchanged.

## Final receipts

Final 7939341f sovereign workflow 39156415478 SUCCESS:49 PASS per interpreter (3.11 in 126.65s;3.12 in 149.72s;2 warnings each). Scope:43 original sovereign authority/B1 cases,4 genuine-signature A2 negatives and2 public restore denial cases. Actual journey25 PASS per interpreter is separately scoped in the customer report. [Sovereign workflow 39156415478](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39156415478), [First Enrollment39156434612](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39156434612), [Independent Integration39156415461](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39156415461).

Final First Enrollment39156434612 FAILURE:12 FAIL/95 PASS per interpreter, Python 3.11 in 126.74s and3.12 in 130.34s. Logs saved `/private/tmp/m13-7939341f-enrollment.log`. Missing-A2 downstream assertions remain unqualified; no original assertion was amended.

Predecessor 296ad7ff andc46dffb5 dedicated scope 49 PASS per interpreter:43 original sovereign authority/B1 cases,4 independent A2 negatives,2 public restore denials. Do not substitute these counts for final receipts. Four added negatives use real PostgreSQL, server ceremonies and genuine private-key signatures, with current email revocation/UV=false/non-server-issued challenge/persisted authenticator revocation; zero roots after denial. Explicit negative state injection is not a customer membership-removal receipt.

## Mandatory-case disposition

| Requirement | Concrete evidence / remaining limit |
|---|---|
| Unverified current email | New real-PG negative; no root after denial |
| Missing passkey/assertion; caller-supplied flags | Original password-only/missing-assertion denials; flags cannot enable root |
| Expired UV | Persisted expired-context denial |
| UV=false | Genuine signed assertion negative |
| Forged challenge | Genuine enrolled key over non-server-issued challenge denied |
| Challenge/root replay | Original ceremony/concurrent completion/replay cases; not universal recovery qualification |
| Session replacement/pre-step-up cookie | Actual elevated-session rotation and old-session401; persisted session denial |
| Revoked membership / suspended tenant | Current persisted state negatives |
| Cross-tenant proof | Ceremony tenant-binding negative |
| Revoked authenticator | New persisted revocation negative |
| Concurrent root completion | Real-PG one-winner/replay denial case |
| Duplicate root error precedence | Protected expected ROOT_ALREADY_EXISTS vs A2_AUTHENTICATION_REQUIRED remains disputed; downstream precedence UNQUALIFIED |
| Root-key/identifier collision | Protected historical tests fail before downstream collision assertions; UNQUALIFIED |
| Successful recovery replay/quorum | Public mutation disabled; original incomplete-setup tests do not prove successful qualified recovery. BLOCKED |
| Stale epoch | Canonical epoch/ceremony state denial |
| Revocation precisely between authorization and final write | Not established solely by pre-completion state injection; independent interleaving acceptance remains UNQUALIFIED |

This matrix records scope, not a blanket claim that every mandatory gate passed. See final workflow/full-suite receipts for actual case outcomes.

## Protected first-enrollment disposition

Twelve historical TITAN root/authority cases persist mailbox verification but do not call authenticate_passkey or provide Actor.session_id from a genuine recent UV session. AST inspection confirmed this for every affected subject. Their failure “Recent verified owner WebAuthn UV is required” is a real policy denial, not proof that the hidden downstream assertion is correct.

The full suite additionally exposes seven older customer-bootstrap HTTP cases: their shared helper verifies email and creates a plain browser session through WebIdentityRepository.create_session, with no passkey enrollment/assertion or recent server-verified UV. These SQLite fixtures consequently fail initiation403 or lack a bootstrap token; later replay/consent assertions are not reached. Together with nine older root-hardening cases and twelve TITAN cases, the final predecessor matrix has28 root-bootstrap failures. This is precise setup evidence, not a blanket claim that their downstream logic is safe or that protected test changes are authorized.

Subjects: pending-quorum recovery precedence, adversarial WebAuthn, concurrent enrollment, unseeded enrollment/bridge, identifier collision, rollback, identifier recycling, pending-principal promotion, IDNA collision, consequential authority chain, multi-admin quorum, cross-tenant escalation. Nine older root-hardening cases similarly predate the new session contract.

Required maintainer action: authorize a specification-compatible supplement using actual server-issued cryptographic UV and current session, preserving original negative assertions and explicit error precedence. No flags, forged assertion, mocked service verifier, seeded elevated session or relaxed guard is supplied. Separate successful sovereign cases do not automatically close these original failures.

Public root recovery create/vote/execute remain unconditionally disabled after authentication/CSRF/tenant checks. Root activation does not qualify legal/founder identity; founder-controlled assurance and reusable credential decisions remain unresolved.
