# Phase 13 — Immutable Audit + Evidence: Design

## Objective

Per the master directive's Phase 13 ("Immutable Audit + Evidence") and
`ENTERPRISE_SECURITY.md`/`THREAT_MODEL.md`'s already-named gap: "No
hash chain without external anchoring (e.g. periodic publication to
write-once storage) can defend against [an attacker with full database
write access recomputing the entire chain from scratch] — we don't
claim otherwise." Per directive rule 63: audit first, close only what
this phase can genuinely deliver without inventing a specific external
storage integration no go-ahead named.

## Audit: what already exists

- **`governance/evidence.py`** — `EvidenceRecord` (pure, unhashed
  shape), `build_evidence_record()`.
- **`db/evidence_repository.py`** — `EvidenceRepository`: per-org hash
  chain (`entry_hash = sha256(prev_hash + fields)`), write-once (no
  `update`/`delete`), `verify_chain()` (re-walks and recomputes every
  hash, returns `False` on the first mismatch).
- **`governance/evidence_bundle.py`** (v3 authority-layer work) — a
  materially more advanced answer to "external anchoring" than the
  audit expected to find: `build_evidence_bundle()` produces a
  self-contained, **offline-verifiable** export (a time-scoped or full
  slice of an org's chain, plus a **bundle-level digest** over every
  included record's own hash) — independently re-implementing the
  entry-hash formula rather than importing the DB layer, so a bundle
  can be verified with zero database access at all.
  `verify_evidence_bundle()` is the offline verifier. Already exposed
  via `/api/governance/evidence/bundle` and
  `/api/governance/evidence/bundle/verify`. Already extensively tested
  (19 tests in `tests/test_evidence_bundle.py`) — field edits,
  reordering, record removal, forged appends, and a tampered
  bundle-digest are all caught.
- **The module's own documentation is already honest about the
  remaining limit**: `evidence_bundle.py`'s docstring states a
  time-scoped bundle's first record's `prev_hash` points to a record
  *outside* the export — "an external anchor, not something the bundle
  alone can verify" — and that a caller needing the full guarantee
  should export the unscoped chain or "separately confirm the anchor
  hash against the live system's own `verify_chain()`."

## The gap that's real, and the gap that isn't

**Not a gap**: the *mechanism* for external anchoring. It already
exists — `build_evidence_bundle()`'s bundle digest is exactly the
artifact a periodic export-and-store-elsewhere process would publish.
Building a second, parallel mechanism would be exactly the unrequested
duplicate-rebuild directive rule 63 prohibits.

**A real gap, correctly out of scope**: *where* to publish it. "e.g.
periodic publication to write-once storage" names no specific backend
(S3 Object Lock, a public transparency log, a customer's own SIEM) —
same shape as Phase 12's KMS/HSM finding (the seam exists; the
concrete cloud/infra-specific integration needs an explicit go-ahead
naming a target, not a default choice made here).

**A real gap this phase closes**: the specific security property that
*justifies* external anchoring in the first place — "a bundle exported
before a full-chain-regeneration attack detects tampering that
`verify_chain()`/`verify_evidence_bundle()`, run only against the
live, already-tampered DB, cannot" — was documented as a claim but
never regression-tested as a concrete, reproducible scenario. Without
this, "external anchoring would help" is an assertion; with it, it's a
demonstrated property.

## Scope for this phase

New file: `tests/test_evidence_chain_anchoring.py`:

1. **The documented limitation, made concrete and reproducible**: seed
   a real chain (including a `DENY`/`QUARANTINE` decision), then
   simulate an attacker with full DB write access — directly UPDATE
   the `governance_evidence` table (bypassing `EvidenceRepository`
   entirely, matching the documented threat model exactly) to change
   the hidden decision's `decision` field to `ALLOW`, and consistently
   recompute every downstream `entry_hash`/`prev_hash` from that point
   forward using the same formula `_compute_entry_hash()` uses. Prove
   `EvidenceRepository.verify_chain()` returns `True` against this
   tampered-but-internally-self-consistent chain — the actual,
   concrete shape of the documented limitation, not just an assertion
   in prose.
2. **The mitigation, proven to actually work**: export a bundle
   *before* the tampering (capturing its bundle digest — the artifact
   an external anchor would store), perform the same tampering as
   above, then export a fresh bundle for the identical time range.
   Prove the two bundle digests differ — an externally-held anchor
   from before the attack detects exactly what `verify_chain()` alone,
   run only after, cannot.
3. **Negative control**: two bundles exported for the same,
   *untampered* range at different times produce the identical digest
   — proving the digest is a function of the records' content, not
   incidentally different for unrelated reasons (e.g. export
   timestamp), which would make the first two tests meaningless.

No source file changes — this phase adds evidence that an existing,
already-built mechanism (`evidence_bundle.py`) delivers the property
`ENTERPRISE_SECURITY.md` says only external anchoring can provide, not
new architecture. No database migration.
