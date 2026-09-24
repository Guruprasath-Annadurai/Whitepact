# Final hardening baseline (recorded)

| Field | Value |
| --- | --- |
| Baseline merge SHA | `b3e9d6072105a25c63b2915658bb74f31296c9a8` |
| Baseline tree | `f49ff56bf9f31ce5a7e15dbfbf533c33245c61e6` |
| Baseline version | `1.3.0` |
| Hardening branch | `cursor/v1.3.1-final-enterprise-hardening` |
| Maintenance target version | `1.3.1` (patch; runtime + security semantics) |
| Production MCP tools | **30** (`production_tool_count()`) |
| `PRODUCTION_GATE_B_OPEN` | `False` |
| `PHASE7A_DISPATCHER_ENABLED` | default **false** |
| CI branch coverage gate | ≥ **80%** |
| CI statement coverage gate | ≥ **90%** |

## Alembic / migrations (repository truth)

Antigravity reported both **57 → 0057** and **61 → 0061**. Repository inspection on baseline tree:

| Check | Result |
| --- | --- |
| Files under `migrations/versions/` | **61** |
| `alembic heads` | **`0061` (head)** |
| Head revision file | `0061_sovereign_shadow_observations.py` |
| Linear chain | **Yes** — `alembic history` resolves to single head without branches |

The **57** figure predates migrations `0058`–`0061` (dashboard SAML transactions, audit key width, test consequential counters, sovereign shadow observations). Documentation must use **61 / 0061**.

## Git status at campaign start

Detached checkout from baseline SHA; worktree untracked: `governance.db`, `release-evidence/`, `worktrees/` (not part of product tree).

## Scope guardrails

- No merge to `main` in this campaign
- No marketplace publish
- Gate B and Phase7A remain off
- MCP production tool count remains **30**
