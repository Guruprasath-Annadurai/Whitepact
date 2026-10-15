# Execution evidence: bounded offline inspection

Run:

```sh
python scripts/evidence/inspect_loaded_export.py whitepact-loaded-evidence.json
```

The current console exports only loaded scalar rows, not the complete canonical
hash preimage, signatures, witness sequence or external attestation. The new tool
validates that format and reports decision/outcome counts, UNKNOWN count and
references to hashes present in the supplied window. It never contacts a server,
prints original record values or creates execution authority.

Matching references are not cryptographic verification: an attacker can forge
both supplied hashes. Missing references may reflect a partial listing. HTTP
success, ALLOW, a hash or a supplied scope string does not prove the external
effect occurred. Output always explicitly says authority_proven=false,
external_effect_proven=false, external_anchor_checked=false and verification is
not possible from this bounded export.

Input is bounded to4MiB and200 records; duplicate JSON keys/IDs/hashes, extra raw
credential fields, nested values, nonfinite numbers and malformed hash references
are rejected. Diagnostics are fixed text, never private payloads or paths.

This improves the inspection workflow under M12 execution-proof research; it is
NOT a new signed Execution Proof product or independent witness verifier.
Canonical complete-payload/witness export requires the security owner's reviewed
contract. Existing witness/verifier implementation must be reused rather than
duplicated in a second authority kernel.
