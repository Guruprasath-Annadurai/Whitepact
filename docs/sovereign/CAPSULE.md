# Sovereign Capsule

Diagnostic export with redaction and SHA-256 digest over canonical payload fields.

- `create_capsule` — redacts secrets via `redact_for_debugger`.
- `validate_capsule` — detects tampering via digest mismatch.
- `reproduce_capsule` — zero-effect metadata replay only (no grants/tokens).

Never includes credentials, raw execution tokens, or reusable grants.
