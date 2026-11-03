# whitepact-community

**WhitePact Community Core** — a small, independently installable local
governance package: Python SDK, MCP stdio server, and CLI.

This package is deliberately **not** the enterprise SaaS platform. It does
not include billing, hosted dashboards, tenant controllers, or commercial
connectors. Enterprise capabilities that require private infrastructure are
reported as unavailable — never simulated as success.

## Status

Internal prototype / qualification candidate (`0.1.0a1`).

- **Not** authorized for public publication by this package alone.
- **Not** a production security certification.
- **M13 OPEN / GLOBAL PRODUCTION NO-GO / M14 LOCKED.**

## Install (local / unpublished)

```bash
python -m pip install -e "packages/whitepact-community[dev]"
```

## Quick start

```python
from whitepact_community import GovernanceClient, ActionRequest, AuthorityGrant

client = GovernanceClient.local()
decision = client.evaluate(
    action=ActionRequest(action_type="local_echo", target="local_echo", arguments={"text": "hi"}),
    authority=AuthorityGrant(delegated_by="local-operator", granted_action_types=frozenset({"local_echo"})),
)
print(decision.decision)  # ALLOW or DENY / ...
```

```bash
wpc --help
wpc version
wpc evaluate --action-type local_echo --target local_echo --grant local_echo
wpc mcp diagnose
```

## Boundary

| Included | Excluded |
| --- | --- |
| Local SDK + policy models | SaaS dashboard / hosted APIs |
| MCP stdio (local tools) | Billing / Stripe / subscriptions |
| CLI | Enterprise identity (OIDC/SAML/MFA) |
| Deny-by-default governance kernel | Production tenant controllers |
| Local evidence hash chain | Proprietary cloud orchestration |

See `docs/ARCHITECTURE_DECISION.md` and `docs/FOUNDER_IP_MATRIX.md`.
