# Concepts

## Authentication vs runtime authority

| Question | Layer | WhitePact component |
|----------|--------|---------------------|
| Who is calling? | Authentication | API keys, org-scoped keys, web sessions |
| May this **specific action** run **now**? | Runtime authority | `WhitePactRuntimeGateway`, delegations, policy |

**Technical access (a valid API key or MCP session) does not imply authority** to
execute high-risk tools. Governed paths reload delegations and apply policy on
each call.

## Control chain (product view)

```
Constitution → Identity → Authority → Intent → Policy → Capability → Risk
  → Approval → Judgment → Short-lived grant → Isolated execution → Evidence → Audit → Revocation
```

Not every deployment enables every stage on day one. The quickstart exercises
**Identity → Authority → Policy (basic) → Evidence → Revocation** locally.

## Decisions

`WhitePactRuntimeGateway.evaluate()` returns one of:

- `ALLOW`
- `ALLOW_WITH_REDACTION`
- `REQUIRE_APPROVAL`
- `DENY`
- `QUARANTINE`

## Package naming

- **PyPI package**: `rai-governance-platform`
- **Python import**: `responsibleai`
- **Product name**: WhitePact

See [`docs/PACKAGE_IDENTITY.md`](PACKAGE_IDENTITY.md).
