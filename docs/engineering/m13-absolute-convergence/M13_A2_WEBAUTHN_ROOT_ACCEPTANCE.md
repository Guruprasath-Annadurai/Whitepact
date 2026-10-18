# M13 A2 WebAuthn/root acceptance

Status: PARTIAL. Founder A2 remains verified mailbox + recent server-verified WebAuthn UV + active current tenant owner + consent + root PoP. This establishes account/authenticator control, not legal identity. No IDENTITY_VERIFIED grant or reusable API-key relaxation.

Historical final-head38f3ceb0 workflow39100554791 passed43 authority tests per Python3.11/3.12. This is predecessor evidence, not final integrated qualification.

Twelve enrollment workflow failures originate in tests/test_m13_titan_root_adversarial.py and tests/test_m13_titan_authority_closure.py. Their setup predates required real session-bound A2; missing UV is a real policy denial, not proof of downstream root/quorum correctness. The recovery case expecting ROOT_ALREADY_EXISTS receives A2_AUTHENTICATION_REQUIRED before revealing root state. Protected original tests remain unchanged and failing; a maintainer must resolve specification precedence and authorize any editable setup extension. No bypass fixtures, seeded elevated sessions, or weakened guard.

Existing sovereign tests cover real cryptographic registration/assertion, expiry, tenant/membership/session state, root PoP, replay, concurrent initialization, epoch/recovery fencing and public recovery denial. Missing mandatory cases must remain UNQUALIFIED until mapped to exact final-head evidence. Public create/vote/execute recovery stays unconditionally disabled pending independent contract qualification.
