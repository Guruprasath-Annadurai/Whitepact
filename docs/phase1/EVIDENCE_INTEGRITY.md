# Phase 1 evidence integrity boundary

WhitePact stores consequential governance decisions in a DB-backed,
tenant-scoped, tamper-evident evidence chain. This is an integrity and ordering
control under the trust assumptions below. It is not blockchain, WORM storage,
non-repudiation, independent notarization, an external timestamp, or legal proof.

## Canonical records

New records use integrity version 2 and `CANONICAL_CHAINED`. SHA-256 covers the
tenant and evidence identifiers, principal and workload identity, authentication
method, action and target, request and argument fingerprints, purpose,
authority/delegation and consent references and versions, policy version,
governance epoch, approval and execution-authorization references, decision,
risk, timestamps, predecessor, and chain sequence. JSON is serialized with
sorted keys, fixed separators, UTF-8, and non-finite numbers rejected.

Raw action arguments are not stored. Their canonical SHA-256 fingerprint and
argument field names are stored. Evidence must never contain API keys,
authorization headers, OAuth tokens, database or Redis credentials, upstream
credentials, field-encryption keys, TOTP secrets, or backup codes.

Evidence is append-only through the repository interface. Corrections are new
records; accepted protected history is not updated. A tenant-owned durable head,
monotonic sequence, uniqueness constraints, database transactions, and row
locking/conflict retry prevent silent forks across application instances.

## Outcomes and ordering

Required decision evidence is committed before consequential dispatch. If that
write fails, dispatch is blocked. Outcomes are separate append-only observations:
`SUCCEEDED`, `FAILED`, `DENIED`, `BLOCKED`, or `UNKNOWN`. `UNKNOWN` means an
external effect may have occurred but WhitePact cannot prove its final state.
Post-dispatch evidence failure never becomes success, denial, fabricated rollback,
or a blind retry. Exactly-once durable authorization consumption does not imply
exactly-once external side effects.

Authenticated governed denials and material replay/security rejections should be
recorded. Unauthenticated protocol noise, malformed traffic, and rate-limit noise
are not accepted into the evidence chain, avoiding an unauthenticated storage DoS
surface. Payloads remain bounded and fingerprinted.

## Verification and legacy records

Tenant-scoped verification returns `VALID`, `INVALID`, `INCOMPLETE`, or `UNKNOWN`.
It checks canonical digests, predecessor links, sequence continuity, and the
durable head. Tenant-scoped lookup does not reveal another tenant's evidence,
outcome, or head.

Pre-0042 records are preserved as `LEGACY_CHAINED_V1`. Their existing limited
hash chain remains verifiable, but WhitePact does not claim those hashes protected
the expanded v2 security context. A chain containing such history is
`INCOMPLETE`, not silently upgraded to canonical proof.

## Trust assumptions and residual risk

The chain assumes the running application and verifier use reviewed code and that
the database provides correct transactional and durability behavior. Hashing
detects changes relative to the persisted chain and head. It cannot defeat an
attacker who can rewrite all database records and trusted anchors, replace the
application/verifier, manipulate backups before verification, or fully compromise
the host. No keyed integrity is introduced because it would not remove those
administrator/host trust assumptions without independent key custody and anchors.

Full retention schedules, legal hold, customer-configurable deletion, backup
attestation, independent timestamping, and privileged-administrator governance are
not implemented by Checkpoint 5. Organization deletion is restricted by evidence
foreign keys. Comprehensive privileged-admin auditing remains not verified.
