# Operation Absolute — active closure ledger

M13 OPEN. GLOBAL PRODUCTION NO-GO. M14 NOT AUTHORIZED.

## Verified entry state

Clean APEX c0e63103b216b8266428cbfee2074d0d876d337d, tree
e46c5739a58c1e21539ff28bb5f7b85f533b1d2b, parent380f86a3.
Canonical remote fetched; TITAN-1 remains2819be09 and TITAN-2 remains622b02d6.
No owner branch changed. Prior exact-head mandatory failures and original
reproducer hashes remain authoritative; no owner report is automatic acceptance.

## Current dependency order

1. Independently qualify policy-independent first-passkey enrollment and fix
   demonstrated write-boundary defects in a separate review proposal.
2. Qualify legitimate and negative enrollment, concurrency and actual PostgreSQL;
   request TITAN-1 review before promoting security-owned changes into APEX.
3. Continue canonical customer-agent credential/judgment integration only against
   verified backend contracts. Founder Record A remains unratified.
4. Complete exact-head integration and compliance gates; keep historical evidence
   and genuinely unqualified journeys blocked.

## ABS-ENROLL-01 — confirmed registration qualification race

Severity: P1 confirmed credential-write boundary violation; blocks P0 first-passkey
acceptance. No public HTTP exploit, root authority grant or session elevation is
claimed by these service tests. A valid password session and ADD_PASSKEY grant
are legitimately established through actual repositories/services. Cryptographic
registration data is generated with the existing WebAuthn test helper.

The controlled scheduler calls the real step-up implementation, then commits
revocation in a separate database transaction before credential persistence.
Unmodified owner2819: organization, membership, session, email, absolute expiry
and idle expiry changes are ignored at the final write. **6 FAIL / 1 PASS in28.63s**.
The positive case confirms registration alone leaves PASSWORD assurance and no
root. This is not a customer journey receipt or hardware authenticator proof.

Root cause: step-up eligibility is checked and consumed in one transaction;
registration subsequently locks only the user and checks credential/replay counts.
It does not revalidate the revocable enrollment context. The optional user lock
also catches and ignores arbitrary database errors.

Isolated proposal: codex/whitepact-absolute-enrollment-review, based exactly on
2819be0938ac88c57dc9a7d0d1215c96d87b35ab. The proposal locks revocable user,
organization, membership and session rows through the write; checks canonical
persisted session expiry/freshness; rechecks eligibility before credential insert;
and propagates lock/read failures. It does not elevate sessions or authorize roots.
The initial strict freshness change rejected legitimate legacy sessions with null
auth_time; corrected to the same created_at fallback used by canonical load_session.
Do not promote before its positive, negative, neighboring and PostgreSQL tests pass.

Reproducer: scripts/engineering/reproducers/test_m13_absolute_first_passkey.py.
All pre-existing immutable reproducers remain unchanged. New fixture variants
exercise SQLite and isolated PostgreSQL; the PostgreSQL-only two-enrollment race
uses a barrier after both actual grants are consumed, not timing-only sleeps.

## Editable Ruff remediation

APEX authority service's nine findings corrected without changing protected tests:
unused imports and unused generated challenge ID removed, redundant UTF-8 encode
argument removed, recovery execution still awaits proof verification/consumption
while discarding only its unused return value. Vote audit metadata still preserves
its proof result. A transient edit of the similarly named vote block was caught by
Ruff before checkpointing and corrected. Source Ruff now PASS; whole-repository
lint remains blocked by protected/historical findings pending exact disposition.

Focused source/security regressions and proposal qualification are running;
no pending result is a PASS. No mandatory gate has been disabled or excluded.

Executed continuation: source cleanup/security neighbors13PASS27.71s; editable
source RuffPASS; full unchanged gate now91 findings (100 minus9 source fixes).
Proposal plus identity neighbors80PASS165.98s; actual PostgreSQL8PASS105.47s,
including one-winner concurrency. Actual owner PostgreSQL session/email baseline
2FAIL27.26s confirms the defect is not SQLite-only. Proposal working-tree genuine
browser17PASS/1BLOCKED/7NOT_EXECUTED; stage17 still credential identity403.
That browser receipt was dirty source, not final committed-head acceptance.
Proposal implementation checkpoint68324f11b0caddc2437255a5929f280dccbe7703;
follow-up test guards require the post-authorization mutation actually committed,
preventing a denial before the intended race from being misreported as success.
Final owner-review PR, committed browser and CI evidence remain pending.
