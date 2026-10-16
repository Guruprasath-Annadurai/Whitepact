# Wave 1 ownership

Starting ancestor: `f338556baf9984ab485f2d4758179fb87e8baa4d` (PR #198; preserved).

Codex Go branch: `codex/whitepact-go-governance-sdk`.
Exclusive write surface: Go governance adapter/tests/examples, dedicated Go qualification workflow,
and new SDK/engineering documentation. MCP compatibility tests run on a separate Codex branch.

Antigravity retains core runtime, billing, revocation implementation, Linux containment,
shared authentication/authority/security files. These are excluded from Codex edits.
SDK revocation methods consume existing HTTP routes; they do not change revocation semantics.

Execution authorization remains server-side. This API has no standalone grant minting
or transferable grant endpoint; the Go SDK must not invent one. A request, API key,
policy response or approval record is not an execution grant.

Production NO-GO. No main merge, deployment, package publication or cloud provisioning.
