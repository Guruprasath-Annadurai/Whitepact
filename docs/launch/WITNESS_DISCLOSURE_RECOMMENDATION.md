# CodeQL alerts 134 / 135 — witness-file disclosure review and recommendation

Founder instruction: **do not auto-dismiss.** Nothing has been dismissed. This document is the
requested review and a recommendation per alert. The decision is the owner's.

Scope: `src/responsibleai/governance/evidence_publication.py` (alert 134 at the public-key `chmod 0o644`,
alert 135 at the publication-record `os.open(..., 0o644)`), rule `py/overly-permissive-file`.

## 1. What the record discloses (verified from the code, not assumed)

`PublishedWitness.to_dict()` writes nine signed fields plus `live_object_store_status`:

| Field | Sensitivity if the file is world-readable |
|---|---|
| `organization_id` | **Tenant identity**: reveals that this tenant exists and is a customer. |
| `chain_sequence` | **Activity volume**: it is the count of evidence entries the tenant has produced. |
| `witnessed_at` | **Timing**: when the tenant was active. |
| `head_hash`, `previous_publication_hash`, `publication_hash`, `signature_hex` | None of substance (hashes/signature). |
| `key_id`, `public_key_hex` | None (public by definition). |

The directory layout is `<witness dir>/<organization_id>/<sequence>.json`, so a listing of the
directory alone enumerates every tenant and a per-tenant listing reveals every publication time.

## 2. Is it actually exposed? (important and previously unstated)

`AppendOnlyWitnessLog` / `publish_evidence_head` are referenced only by `governance/evidence_witness.py`.
**No HTTP route in this repository serves the witness directory.** World-readable *file mode* is
therefore not by itself public *exposure*: exposure happens only if an operator serves the directory
(static host, bucket, CDN). The alert is a file-mode finding on a design whose purpose is public
verification; the real question is what a deployment would publish. No deployment of this exists yet
(live anchoring is not provisioned — REC-13).

## 3. Per-alert recommendation

| Alert | File | Recommendation |
|---|---|---|
| **134** (public key `0o644`) | `<keys>/public/<key_id>.pub` | **Safe to dismiss as "won't fix" *when the owner agrees*.** The file holds only an Ed25519 *public* key, which must be readable by verifiers; no tenant information. The private key stays `0600` in a `0700` directory and `current_private()` refuses a loosened key. Owner action only. |
| **135** (record `0o644`) | `<witness>/<org>/<seq>.json` | **Do NOT dismiss yet.** The record carries tenant identity, activity volume and timing (section 1). Either (a) adopt the v2 record below, after which it is equivalent to 134 and can be dismissed, or (b) the owner records an explicit decision that tenants accept publication of id/volume/timing. Until then the honest status is *open, mitigated by non-exposure*: nothing in this repo serves the files. |

## 4. Options evaluated

**A. Keep format, document the disclosure.** Cheapest; tenant id, volume and timing are public to
whoever can read the directory. Acceptable only with explicit tenant consent in the terms.

**B. Versioned opaque tenant reference (`witness_ref`, record v2).**
Replace `organization_id` in the record and the directory name with a per-tenant random 128-bit
`witness_ref` stored in the database, and add `"record_version": 2` inside the signed material.
- Preserves public verification: a verifier needs only the ref (given to them by the tenant or
  shown in the tenant's evidence bundle), the public key and the log.
- Removes *identity* disclosure and makes the directory non-enumerable (an unguessable name, listing
  disabled at the host).
- Does **not** remove volume/timing disclosure for a given ref. A third party who learns a ref learns
  that pseudonym's activity. Do not describe this as "anonymous".
- Needs: schema/migration for the ref, a dual-read verifier (v1 + v2) so existing records still
  verify, an owner-visible mapping ref↔org inside the authenticated bundle, and an Antigravity
  review (it touches the evidence trust root).
- Do not derive the ref from the org id with an unkeyed hash (dictionary-attackable) or a keyed
  hash whose key is lost on rotation; a stored random value avoids both.

**C. Publish a batched cross-tenant root only.** On a fixed interval publish one signed Merkle root
over all tenants' heads; give each tenant its inclusion proof privately. The public log then reveals
no per-tenant identity, volume or timing, and verification is still independent. Largest change;
the strongest privacy; recommended as the *target* design, with B as the step that fits the current
code. Not started.

**D. Do not serve publicly; serve verifiers authenticated.** Remove the "public" premise: tenants
(and auditors they authorize) fetch their own records over an authenticated route. Simplest
confidentiality, weakest independence claim (the operator controls access). Compatible with B/C.

## 5. Recommendation

1. Treat 134 as dismissible *by the owner* (public key only).
2. Keep 135 **open**. Implement **B** (versioned opaque `witness_ref`, dual-read verifier) and make
   the serving rules part of the runbook (listing disabled, no index). Then 135 describes a file whose
   content is non-identifying and can be dismissed with a precise comment. Plan **C** as the longer
   term privacy design.
3. Until then make no claim that the witness log is private, anonymous, or externally immutable.

## 6. Retest evidence (run on this tree)

Command: `pytest tests/test_evidence_publication.py`. Result recorded in the register entry REC-36
after the run completes (see below). The suite covers: private key mode and refusal of a loosened
key; exactly nine record fields; no private key bytes in any public file; directories not
group/world-writable even with `umask 0`; `O_EXCL` no-overwrite; rollback/rewrite/gap/missing-file
detection; publication-hash tamper detection; key rotation keeps old verification; witness material
not copied into agent execution. These confirm permissions, record integrity, key confidentiality
and independent verification **of the current v1 format**. They do not exercise a v2 format, which
does not exist yet.

## 7. Update 2026-10-11: record v2 (opaque tenant reference) is implemented

Founder decision: resolve the tenant-identity concern, verify the design, propose an exact disposition. Done in code; **nothing is dismissed.**

**Design.** `publish_evidence_head(..., opaque_reference=True)` is now the default. The log directory, the signed subject and the published record use
`witness_ref = "wr1_" + base32(HMAC-SHA256(secret, "whitepact-witness-ref-v1\0" + org_id)[:16])`. The 32-byte secret lives in
`<keys>/private/witness_ref.key` (0600, refused if loosened). The v2 record has `record_version: 2` and `witness_ref` and **no
`organization_id`** (signed: the publication hash covers both). v1 records still read and verify. A record copied into another
tenant's directory is refused on read (subject must match its location).

**Verified by test (`tests/test_witness_opaque_reference.py`, 8; `test_evidence_publication.py`, 23, unchanged semantics for v1):**
no tenant identifier in any public file or path; exact v2 field set; references stable, distinct per tenant and not derivable
without the secret; secret is 0600 and never in the public tree; independent verification from the reference alone after
reopening the log (rollback, rewrite and missing-record detection intact; the real org id resolves to nothing); tamper and
version-downgrade detection; cross-tenant copy refusal.

**What it does not do.** It removes tenant *identity* from the public record. It does **not** hide *activity volume and timing*
for a given reference (`chain_sequence`, `witnessed_at`), and anyone who learns a reference learns that pseudonym's activity.
Losing the secret makes existing references unrecoverable. No live external anchor exists (REC-13). The directory must still be
served without a listing so references are not enumerable. No production caller publishes to a served directory yet.

**Proposed exact dispositions (owner to approve; not applied):**
* **Alert 134** (`public key 0o644`): dismiss as *won't fix*. Comment: "Ed25519 public verification key; must be world-readable for independent verification; private key is 0600 in a 0700 directory and refused if loosened (tests/test_evidence_publication.py); no tenant data."
* **Alert 135** (`record 0o644`): dismiss as *won't fix* **only if the owner accepts the residual volume/timing disclosure per opaque reference**, and only after Antigravity independently confirms section 7. Comment: "Public witness record (record_version 2) contains no tenant identifier or secret; publicly verifiable by design; residual activity-volume/timing per opaque reference accepted by the owner on <date>; see docs/launch/WITNESS_DISCLOSURE_RECOMMENDATION.md." If the owner does not accept the residual, adopt the batched cross-tenant root (option C) instead and keep 135 open.
* No blanket suppression and no path-level exclusion of `py/overly-permissive-file` is proposed.
