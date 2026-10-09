# Phase 6 — Security assault results

**Gate: CONDITIONAL for the two local defects. NOT EXECUTED for a penetration test.**

No penetration-test certificate is claimed. No public target was attacked. No production credential was used.

## Executed in this session

| Case | Result |
|------|--------|
| Delegated `memory_scope` wider than parent | Denied after the fix. Regression tests pass. |
| Delegated `memory_scope` unset while parent is set | Denied. |
| Sibling prefix `org:acme` vs `org:acme2` | Denied. |
| Descendant scope | Not an escalation. |
| Gateway evaluate with widened scope | `DENY` and `DELEGATION_AUTHORITY_ESCALATION`. |
| Unsigned commit against the DCO workflow script | Exit 1 in `tests/test_dco_historical_exception.py`. |
| Movable `- uses: actions/checkout@v4` | Detected by `unpinned_references`. Repository workflows scan clean after the pin. |
| Evidence checker given only the green CI URL | Exit 1, decision `NO-GO`. |

## Present on the candidate and not re-executed here

WAR-8 harnesses and governance suites already in the tree cover, at code level: prompt-injection memory firewall patterns, MCP authority matrix, egress cross-challenge, tenant isolation, replay, and revocation. Their prior Antigravity results attach to older SHAs (M4, M5, M6), not automatically to this successor.

## Not executed

- Malicious MCP server against a live worker
- Container escape
- SSRF against a routable network
- Load test against staging
- Backup key-loss drill
- Rate-limit bypass on a deployed edge
- Dependency confusion against a public registry

## Gate

CONDITIONAL locally. The live assault list remains NOT EXECUTED.
