# Founder IP Decision Matrix — Community Package Architecture (A005)

**Status:** Engineering recommendation only — **not** Founder publication authorization.  
**Protected public allowlist:** remains **empty** unless steward-approved.

## Classification legend

| Code | Meaning |
| --- | --- |
| C | Recommended Community Core (this prototype) |
| P | Private / enterprise — keep out of community artifacts |
| H | Historical disclosure issue requiring Security/Legal disposition |
| U | Unsubstantiated in audited accessible sources |

## Recommended narrow community manifest (exact)

```
packages/whitepact-community/pyproject.toml
packages/whitepact-community/LICENSE
packages/whitepact-community/README.md
packages/whitepact-community/MANIFEST.in
packages/whitepact-community/src/whitepact_community/__init__.py
packages/whitepact-community/src/whitepact_community/version.py
packages/whitepact-community/src/whitepact_community/errors.py
packages/whitepact-community/src/whitepact_community/reason_codes.py
packages/whitepact-community/src/whitepact_community/models.py
packages/whitepact-community/src/whitepact_community/risk.py
packages/whitepact-community/src/whitepact_community/policy.py
packages/whitepact-community/src/whitepact_community/evidence.py
packages/whitepact-community/src/whitepact_community/revocation.py
packages/whitepact-community/src/whitepact_community/authorization.py
packages/whitepact-community/src/whitepact_community/gateway.py
packages/whitepact-community/src/whitepact_community/config.py
packages/whitepact-community/src/whitepact_community/sdk.py
packages/whitepact-community/src/whitepact_community/cli.py
packages/whitepact-community/src/whitepact_community/mcp_server.py
packages/whitepact-community/src/whitepact_community/release_control.py
packages/whitepact-community/src/whitepact_community/py.typed
packages/whitepact-community/security/PRIVATE_MODULE_DENYLIST.txt
packages/whitepact-community/security/release_exporter.py
packages/whitepact-community/scripts/verify_package_boundary.py
packages/whitepact-community/tests/
packages/whitepact-community/docs/
```

All of the above: **C** (prototype). Publication still requires Founder/steward allowlist update.

## Private enterprise (remain P)

| Area | Paths (OSS candidate) | Decision |
| --- | --- | --- |
| Dashboard/SaaS | `src/responsibleai/dashboard/**` | P |
| Billing | `src/responsibleai/billing/**` | P |
| DB/tenant | `src/responsibleai/db/**` | P |
| Auth enterprise | `src/responsibleai/auth/**` | P |
| Webhooks | `src/responsibleai/webhooks/**` | P |
| MCP licensing | `src/responsibleai/mcp/licensing.py` | P |
| Hosted MCP HTTP | `mcp/server.py:main_http` | P |
| Broad wheel | `rai-governance-platform` hatch packages | P for community boundary purposes |
| Heart/sovereignty extras beyond local kernel | `sovereignty_kernel.py` et al. | P until explicit Founder classification |

## Historical disclosure registers

| Register | Disposition |
| --- | --- |
| First 13 confidential business documents (FOUNDER_ACTION_CHECKLIST, GAME_CHANGER_*, STRATEGY_ROADMAP, compliance sales/legal memos, etc.) | **H** — real historical PyPI sdist publication issue; Security/Legal disposition required. Verified absent from current OSS candidate tree screening narrative; do not reintroduce. |
| Second 13-path register | **U** — unsubstantiated in audited accessible sources for this session unless new evidence emerges. |

## Prior MIT artifacts

Previously published MIT `rai-governance-platform` artifacts do **not** automatically authorize future source publication or allowlist expansion.
