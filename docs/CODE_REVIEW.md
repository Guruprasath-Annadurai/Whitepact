# WhitePact Code Review Standard

WhitePact uses pull requests as the review boundary for proposed changes. This document defines what a reviewer should check and what makes a change acceptable. It does **not** claim that WhitePact currently satisfies OpenSSF Gold's separate two-person-review percentage requirement; the project is still founder-led and that organizational criterion must be earned through real independent review history.

## Review scope

A reviewer should evaluate the complete proposed change, including source, tests, migrations, workflows, documentation, generated security evidence, and deployment implications where relevant.

## Required review checks

A review should check, as applicable:

1. **Correctness** — behavior matches the stated requirement and error paths are handled deliberately.
2. **Tests** — functional changes have meaningful automated tests; bug fixes should include a regression test when practical; security fixes must preserve the failing case as a regression test.
3. **Authorization** — authentication must not be confused with authority; tenant, role, purpose, target, expiry, revocation, and delegation boundaries must not be widened accidentally.
4. **Fail-closed behavior** — missing or invalid security context must not silently become permission for consequential operations.
5. **Tenant isolation** — data access must remain scoped to the correct organization and cross-tenant identifiers must not be trusted without enforcement at the repository/service boundary.
6. **Input and network safety** — untrusted input is validated; SQL is parameterized; caller-controlled URLs use the established SSRF protections; shell/process execution does not interpolate untrusted text.
7. **Secrets and privacy** — secrets, API keys, credentials, PII, governance-sensitive values, and other protected information are not added to source, logs, metrics, traces, fixtures, or error responses.
8. **Cryptography** — changes use established libraries and existing crypto abstractions; no custom cryptographic construction is introduced without a documented security design and dedicated review.
9. **Dependencies and supply chain** — a new dependency has a clear need, acceptable license, maintained upstream, and no unresolved release-blocking vulnerability; GitHub Actions remain pinned to immutable commit SHAs.
10. **Backward compatibility and migrations** — public API/schema changes are intentional, migrations are safe, and rollback/compatibility implications are documented where relevant.
11. **Documentation truthfulness** — implementation claims match runtime behavior; no certification, penetration-test, medical, enterprise-readiness, or other assurance claim is made without evidence.
12. **Operational impact** — configuration, observability, failure behavior, resource use, rollout, and rollback are considered for production-affecting changes.

## Security-sensitive changes

Changes touching authentication, authority, governance decisions, execution permits, credentials, tenant isolation, cryptography, audit/evidence, MCP tool execution, release workflows, or neural-data security require explicit security-focused review against the relevant threat model and invariants. A green automated scan does not replace that review.

## Acceptance criteria

A pull request is technically acceptable only when:

- required CI checks are green;
- required DCO sign-offs are present;
- blocking review findings are resolved or explicitly rejected with reproducible evidence;
- required tests and documentation are updated;
- no known Critical or High security defect introduced by the change remains unresolved; and
- the change does not obtain approval by weakening an existing security gate.

## Independent review status

WhitePact currently has a single primary maintainer. Therefore this document establishes **review standards**, but does not by itself satisfy the OpenSSF Gold `two_person_review`, `bus_factor`, or `contributors_unassociated` requirements. Those are tracked as organizational maturity requirements and will only be marked Met after real project history satisfies them.
