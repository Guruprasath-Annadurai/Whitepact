# Start here (WhitePact product docs)

WhitePact is a **runtime authority layer** for autonomous agents: authentication
establishes identity; **authority** decides whether a specific action may run now.

This journey is for **strangers** evaluating the project without founder help.
Formula Ω∞ research lives under [`docs/formula/`](formula/) and is not required
for first success.

## Recommended path

| Step | Document | Outcome |
|------|----------|---------|
| 1 | [Concepts](concepts.md) | Auth vs authority, control chain at a glance |
| 2 | [Quickstart](quickstart.md) | First governed allow/deny/evidence/revoke |
| 3 | [Installation](installation.md) | pip, Docker, Helm |
| 4 | [MCP quickstart](mcp-quickstart.md) | 30 production MCP tools — auth ≠ authority |
| 5 | [Authority model](heart-production/01_AUTHORITY_CONTRACT.md) | Delegation, grants, revocation |
| 6 | [Policy](heart-production/00_CURRENT_RUNTIME_MAP.md) | Where policy runs in the stack |
| 7 | [Evidence / audit](phase1/EVIDENCE_INTEGRITY.md) | Hash-chained records |
| 8 | [Operations](VERIFY_RELEASE.md) | Release verification |
| 9 | [Security](security/AUTH_INCIDENT_RESPONSE.md) | Incident and auth guidance |
| 10 | [Troubleshooting](troubleshooting.md) | Common failures |
| 11 | [API examples](examples/http_governance.md) | curl + Python patterns |

## Also useful

- [`README.md`](../README.md) — feature overview and PyPI install
- [`examples/`](../examples/) — numbered tutorials (`08_whitepact_enterprise_scenario.py` is the deep dive)
- [`docs/integrations/README.md`](integrations/README.md) — MCP clients (Cursor, Claude, etc.)
- [`docs/launch-readiness/WHITEPACT_STRANGER_ONBOARDING_AUDIT.md`](launch-readiness/WHITEPACT_STRANGER_ONBOARDING_AUDIT.md) — onboarding gap analysis (Cell A)
