# Security Remediation Gap 5 — Audit Full-DB Compromise: Phase 1 (External Anchor)

## Reproduction

Independently re-verified: `EvidenceRepository.verify_chain()`
(`db/evidence_repository.py`) re-walks an org's entire hash chain from
genesis and recomputes every entry's hash — full, not spot-check. But
`tests/test_evidence_chain_anchoring.py` (Enterprise Neural Phase 13)
already proved this alone cannot detect the directive's named threat
model: an attacker with **full database write access** can tamper one
row and regenerate every downstream hash so the chain still looks
internally consistent — `verify_chain()` reports it intact regardless,
because it only ever re-checks rows already sitting in the same
compromised database. Phase 13 built the artifact an external check
would need (`EvidenceBundle.bundle_digest`,
`governance/evidence_bundle.py`) but explicitly did not build the
external anchor itself (`docs/enterprise-neural/13_PHASE13_DESIGN.md`
names this as future work, not a gap it silently glossed over).

Against the directive's target pipeline — Event → Canonical
Serialization → Hash → Signature → Global Sequence → Primary Evidence
Store → External Periodic Anchor → Immutable/WORM Destination — what
already existed before this phase:

| Leg | Status before this phase |
|---|---|
| Event → Hash → Primary Evidence Store | Built (`db/evidence_repository.py`) |
| Canonical Serialization | Thin — pipe-joined subset of fields, not full-record canonical JSON |
| Signature | **Missing** — `KeyPurpose.AUDIT_ANCHOR` existed since Enterprise Neural Phase 2 but was referenced nowhere |
| Global Sequence (safe across replicas) | **Missing** — ordering is per-org `recorded_at`-string plus a per-process `asyncio.Lock`; no cross-replica coordination |
| External Periodic Anchor | **Missing entirely** — no interface, no implementation |
| Immutable/WORM Destination | **Missing entirely** |

## What this phase builds

`src/responsibleai/governance/audit_anchor.py` (new module):

- **Signature**: `build_and_sign_anchor()` HMAC-SHA256-signs an
  `EvidenceBundle.bundle_digest` under a key resolved via the existing
  `KeyProvider` Protocol and `KeyPurpose.AUDIT_ANCHOR` — the first
  real use of that key purpose since it was defined. HMAC, not
  asymmetric — an honest scope limit named directly in the module
  docstring (proves no post-anchoring forgery by anyone without the
  key; does not give third-party non-repudiation the way a published
  public key would).
- **External anchor interface**: `AuditAnchorProvider` (Protocol,
  `publish()`/`fetch()`, no crypto/DB coupling) — the extension seam
  for a real S3-Object-Lock/RFC-3161/notary backend later, without any
  call site changing.
- **One real, production-capable implementation**:
  `LocalFileAnchorProvider`, using create-exclusive file writes
  (`os.O_CREAT | os.O_EXCL`) so a second `publish()` under the same
  `anchor_id` raises `AnchorAlreadyPublishedError` rather than
  silently overwriting — the one append-only property a local
  filesystem can actually provide. Named `LocalFileAnchorProvider`,
  not `WORMAnchorProvider` — it is explicitly **not** real hardware
  WORM/Object Lock, matching this codebase's own `LocalEnvelopeKeyProvider`
  precedent (Gap 1): one honest, testable, production-capable seam,
  never a fabricated capability.
- **Publication**: `publish_anchor()` — a callable a scheduler or
  admin action can invoke; not itself wired into any background job
  this phase (see below).
- **Verification / compromise detection**:
  `verify_anchor_from_provider()` — fetches the anchor from the
  *external* destination (never the primary DB), verifies its HMAC
  signature, and compares its anchored digest against a digest the
  caller computed **fresh**, from the live evidence store's current
  state. This is the actual fix: an attacker who tampers the DB and
  regenerates the chain forward cannot also rewrite what was already
  published externally before the tamper, so the freshly recomputed
  digest diverges from the anchored one and verification reports
  `DIGEST_MISMATCH`.
- **Raw-neural-data guard** (`tests/test_no_raw_neural_data_in_evidence.py`):
  the directive's explicit requirement ("raw neural data must never
  enter audit evidence") already held true today, but only by
  construction — no code path connected `governance/neural/` to
  `governance_evidence`. This phase turns that accidental truth into
  an enforced guard: `EvidenceRecord`'s fields are checked for any
  payload/signal-shaped name, and every file under `governance/neural/`
  is scanned for a direct `EvidenceRecord(`/`build_evidence_record(`
  call — a future change wiring the two together must now fail one of
  these tests and update them deliberately, not slip through silently.

## Verification of the compromise-detection claim

`tests/test_audit_anchor.py::TestAnchorDetectsFullDbCompromise` reruns
`test_evidence_chain_anchoring.py`'s own attack scenario — tamper one
record's `decision` field and regenerate the chain forward — this time
with a genuine anchor published *before* the tamper. Where the earlier
tests could only prove the attack was undetectable, this phase's tests
prove `verify_anchor_from_provider()` now detects it
(`DIGEST_MISMATCH`), with a companion test confirming the untampered
case still verifies `VALID` under the identical setup (so the failure
is genuinely about tampering, not a harness bug).

## What this phase deliberately does not do

- **Does not fix multi-instance sequencing safety.**
  `db/evidence_repository.py`'s per-process `asyncio.Lock` and
  `recorded_at`-string ordering are unchanged. Making sequencing safe
  across concurrent replicas needs a real change to the hot evidence
  write path (a DB-level atomic sequence or row lock) that this phase
  did not attempt without the ability to test it under genuine
  multi-replica concurrent load — attempting it untested would risk
  the opposite of this remediation's own goal. Named here as the clear
  next item, not silently skipped.
- **Does not strengthen the underlying per-entry canonical
  serialization.** `_compute_entry_hash()`'s pipe-joined field subset
  (both in `db/evidence_repository.py` and duplicated in
  `evidence_bundle.py`) is unchanged. A genuinely complete "Canonical
  Serialization" leg would hash the full record via structured
  canonical JSON, matching `root_authority.py`/`consent_proof.py`'s
  own `_canonical_json()` convention — changing the existing, already
  hash-chained entry format is a higher-risk, migration-shaped change
  (every historical row's hash would need re-derivation or a
  versioned format), scoped out of this phase deliberately.
- **Does not wire periodic publication into any live request path or
  scheduler.** `publish_anchor()` is a callable, not a cron job or
  background task — actually scheduling "anchor every org's chain
  every N minutes" and persisting `AnchorRecord`s for operator/auditor
  retrieval is real, separate wiring work.
- **Does not implement a real WORM/S3 Object Lock/RFC 3161 provider.**
  `LocalFileAnchorProvider` is the one real implementation this phase
  ships; a cloud-backed provider with real regulatory-grade immutability
  is a distinct, infrastructure-dependent piece of work the
  `AuditAnchorProvider` Protocol is deliberately shaped to accept
  without any call-site change.

## Verification

- 14 new tests (11 `tests/test_audit_anchor.py` + 3
  `tests/test_no_raw_neural_data_in_evidence.py`), all passing.
- `ruff check` / `ruff format --check` clean.
- `mypy src/responsibleai`: clean, 167 source files.
- Full repository suite: see commit for the exact pass count at time
  of commit, run fresh.
