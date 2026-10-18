# SOVEREIGN-RECOVERY-01 — independent recovery qualification BLOCKED

M13 OPEN. GLOBAL PRODUCTION NO-GO. Owner handoff: Antigravity / independent
security maintainers. No FORTRESS implementation or test was imported or changed.

Independent read-only review identified a publicly wired alternate canonical-root
writer through customer recovery creation, voting and execution. Existing service
code accepts caller-selected quorum thresholds, does not establish an existing
target root before request creation, and inserts a replacement canonical root
without checking that revocation updated an existing target. Recipient mailbox
qualification, replacement-key PoP and mandatory WebAuthn are not independently
established by this path. Approved recovery may legitimately differ from fresh A2
enrollment; the missing recovery policy must not be invented by product code.

Finding: inherited P1 authority-contract gap, confirmed by source inspection.
The component HTTP regression reproduced acceptance of a request with an
unqualified caller-selected recovery contract in an isolated PostgreSQL database
using a genuine verified, WebAuthn-UV owner and actual A2 root. It did NOT execute
replacement-root recovery or claim an end-to-end exploit. RED on the unguarded
API is separate from the confirmed source concern.

Product boundary mitigation: authenticated customer POST create/vote/execute now
returns503 RECOVERY_SECURITY_QUALIFICATION_REQUIRED, unconditionally. No feature
flag or caller assurance parameter can enable these writes. Existing cookie,
CSRF and tenant checks remain; unauthenticated/cross-tenant/invalid-CSRF requests
are denied. Read-only recovery inventory remains available. The customer UI was
already read-only. The regression verifies unchanged root and recovery rows.

The security-owned service, original reproducer assertions and historical
quorum implementation remain preserved. Their root-cause qualification is
BLOCKED, not fixed or accepted by this boundary mitigation. Internal use must
not be interpreted as a qualified customer contract. Search found no other
production callers of these three service methods beyond the now-blocked routes.

Before reopening customer mutations, independent owners must establish:

* Existing target/root/key/organization binding and atomic checked transitions.
* Approved configured quorum policy and eligible, active, current voters.
* Mandatory server authentication and recipient assurance appropriate to recovery.
* Replacement-key proof of possession bound to a server-created request/nonce.
* Replay, expiry, concurrent recovery/bootstrap, epoch and revocation fencing.
* Consent continuity and justified recovery of authority, with real PostgreSQL
  and genuine authenticated API evidence rather than seeded success.

Unchanged historical tests currently stop at A2 setup and therefore do not
execute their downstream recovery assertions. They remain failing/unqualified.
Fresh-root A2 and development B1 customer receipts do not close this finding.
Other low-level trust-bootstrap/principal-promotion managers had no confirmed
public route in this review; their public reachability is UNVERIFIED.
