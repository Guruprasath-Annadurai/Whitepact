# CodeQL disposition proposal for owner review

Status: **PROPOSAL. Nothing has been dismissed.** Dismissing a code-scanning alert is the owner's decision.
Evidence is for the exact tree named in the PR description; re-read the alert list on the new head before acting.

## Alerts that were fixed in code (do not dismiss)

| Alerts | Rule | What was wrong | Fix |
| --- | --- | --- | --- |
| 121, 122, 131, 132 | `js/xss`, `js/client-side-unvalidated-url-redirection` | The legacy shell login assigned `?next=` to `location.href` unchecked (`javascript:` and `//host` targets). | Same-origin absolute path only; everything else becomes `/`. |
| 123-130 | `js/incomplete-html-attribute-sanitization` | `escHtml` (15 copies) escaped `& < >` but not quotes, and its output was placed in attributes: `" onmouseover=...` broke out. | Quotes escaped in all 15 pages; changelog / checkout / SSO targets limited to http(s). |
| (default branch) 80, 81, 83, 86, 87, 96 | stack-trace exposure, cookie injection, clear-text logging | See register REC-23. | Fixed with tests. |

The community app serves these pages (unified/production mode blocks them), so the earlier description of them as "unreachable or merely moved" was wrong. Tests execute the shipped JavaScript with Node: `tests/test_legacy_shell_dom_safety.py`.

## Alerts proposed for dismissal by the owner (not done)

| Alerts | Rule | Location | Proposed reason |
| --- | --- | --- | --- |
| 134 | `py/overly-permissive-file` | `evidence_publication.py`, `public_path` chmod `0o644` | Won't fix: intentionally world-readable public key |
| 135 | `py/overly-permissive-file` | `evidence_publication.py`, publication record `os.open(..., 0o644)` | Won't fix: intentionally world-readable public record |

### Why these files are public

The evidence witness exists so that someone **other than the database operator** can check that the evidence chain was
not rewritten or rolled back. A record is useful only if independent verifiers can read it. Restricting it to the owner
defeats the control. It contains no secret: it holds the organization id, chain sequence, head hash, timestamp, key id,
the Ed25519 **public** key, the signature, and the previous publication's hash.

### The boundaries that make that safe, with tests

| Boundary | Mechanism | Test |
| --- | --- | --- |
| **Confidentiality of the private key** | `private/` is `0700`, `current.key` is `0600`, and `current_private()` refuses a key that is group- or world-accessible. The key is never written under `public/` or into a record. | `test_private_key_mode_and_required_failure`; `test_public_witness_material_never_contains_private_key_bytes` (scans every public file for the raw and hex key) |
| **What is disclosed** | The record has exactly nine fields. | `test_public_record_fields_are_exactly_the_documented_set` |
| **Publication authority** (who may add or replace records) | Write access to the directories is the authority, so they are `0755`, never group/world-writable, **independent of umask**. Files are created `O_EXCL`; an existing sequence is never overwritten and a non-newer sequence is refused. | `test_witness_directories_are_not_writable_by_group_or_other_even_with_umask_zero` (fails on the old code); `test_a_published_sequence_cannot_be_overwritten_in_place` |
| **Integrity** | Each record is signed and carries the hash of its predecessor plus its own hash. Rollback, rewrite, gap and missing file are detected from the log alone. | `test_rollback_rewrite_gap_and_missing_publication_are_detected`; `test_rewritten_publication_file_breaks_the_publication_hash` |
| **Agents cannot reach it** | Witness material is not copied into agent execution environments. | `test_witness_material_is_not_copied_into_agent_execution` |
| **Rotation keeps old verification working** | Previous public keys are retained. | `test_key_rotation_keeps_the_previous_public_key` |

### What the owner should decide, and what is still open

1. Dismiss 134 and 135 as "won't fix" with a comment pointing at this document, **or** replace `0o644` with a code
   path CodeQL accepts. The latter is not recommended: widening or narrowing the mode changes who can verify.
2. **Design question, not a CodeQL question:** the public record contains the organization id, the chain sequence and
   timestamps. In a *publicly* served witness log that reveals that a tenant exists and how active it is. If tenants
   consider that confidential, the id should be replaced by a per-tenant opaque identifier. That changes the record
   format and every verifier, so it needs an owner decision and an Antigravity review. Not changed here.
3. **Live anchoring is not provisioned.** The file log is local. `live_object_store_status()` reports that honestly, and
   no claim of external immutability is made. The object-lock transport now requires an https origin and never follows
   a redirect (register REC-13).
