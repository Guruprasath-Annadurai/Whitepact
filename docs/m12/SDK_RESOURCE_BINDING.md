# SDK opaque resource binding

Python, TypeScript and Go governance clients now reject malformed opaque resource
IDs before authentication headers are sent. Dot segments, path/query/fragment
delimiters, percent-encoded input, whitespace/control characters, invalid Unicode
and empty/non-string values cannot alter the intended approval, delegation or
evidence route. Valid IDs are encoded once, not trimmed or normalized.

This is client request-shape protection, not a new authorization boundary.
Server-side tenant/authority/consent checks remain mandatory. A malicious client
can ignore this helper; no SDK-only control is called enforcement.

Before correction, the Python regression suite failed95 cases, TypeScript failed
the new rejection check, and the existing Go validator dispatched40 malformed
requests to an isolated server. Root reproduced these before editing. Go rejected
several delimiter cases already; the new change closes whitespace/control/UTF-8
gaps without removing the older protection.

No backend endpoint or grant type was added. Legacy get_evidence/getEvidence
remains unavailable on the current backend; use its supported attestation route.
UNKNOWN is retained. No unsafe retry, browser tenant authority, key disclosure,
server idempotency guarantee or automatic reconciliation was introduced.

Current regression tools: tests/test_sdk_resource_identifiers.py,
sdk/typescript/test/resource-identifiers.test.mjs and
sdk/go/raiclient/resource_identifiers_test.go. Valid UUID-like, colon-qualified,
underscore, dot-containing and Unicode identifiers remain supported.
