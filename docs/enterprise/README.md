# Evaluate WhitePact for an autonomous-agent workflow

This page is the shortest path for an enterprise architect or security reviewer.
WhitePact is early-stage open-source software; this evaluation path is not a
claim of third-party deployment, operational effectiveness, or certification.

## Start with the boundary

1. [Architecture](../../ARCHITECTURE.md) and
   [enforcement boundary](../../ENFORCEMENT_BOUNDARY.md)
2. [Security architecture](../../ENTERPRISE_SECURITY.md) and
   [threat model](../../THREAT_MODEL.md)
3. [Five-minute local evaluation](../QUICKSTART.md)
4. [MCP setup and capability source of truth](../mcp/README.md)
5. [Release verification](../VERIFY_RELEASE.md)
6. [Current trust evidence and blockers](../../compliance/WHITEPACT_TRUST_STATUS.md)
7. [Public claim boundaries](../../compliance/PUBLIC_TRUST_CLAIMS.md)

## Suggested evaluation

- Pick one bounded, reversible agent action.
- Define the agent identity, delegated action types, limits, and approval rules.
- Verify ALLOW, REQUIRE_APPROVAL, and DENY paths before connecting an executor.
- Confirm denied and approval-pending actions cannot reach that executor.
- Inspect evidence for organization separation and absence of raw argument values.
- Verify the exact release artifact before deployment.
- Run your own threat modeling, tenant-isolation tests, and penetration testing
  against the deployment architecture you will operate.

## Participate without implied endorsement

- [Request or perform an independent security review](https://github.com/Guruprasath-Annadurai/Whitepact/issues/56)
- [Verify an MCP client](https://github.com/Guruprasath-Annadurai/Whitepact/issues/57)
- [Propose a design-partner workflow](https://github.com/Guruprasath-Annadurai/Whitepact/issues/58)
- [Contribute](../../CONTRIBUTING.md)

Participation in an issue does not imply that an organization uses or endorses
WhitePact.
