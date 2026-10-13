# Phase 8 — Technical public claims register

Claims below are limited to what this repository and the recorded CI run support. Draft language is not a public announcement.

| Claim | Allowed now | Evidence | Forbidden extension |
|-------|-------------|----------|---------------------|
| WhitePact enforces runtime authority separately from model output | Yes, as a description of the gateway | `src/responsibleai/governance/gateway.py` | "Cannot be bypassed" without the independent retest of the successor |
| Memory delegation cannot widen `memory_scope` | Only after the successor is the reviewed SHA | `validate_attenuation` fix and tests | Saying `0cdef394` already has the fix |
| Python 3.11 and 3.12 CI green | Yes for `0cdef394` only | Actions run `37900487645` | Saying the successor CI is green |
| Pure branch coverage at least 80% and statement coverage at least 90% | Yes for that CI run | 3.11: 80.90% branch, 91.37% statement. 3.12: 81.27% branch, 91.51% statement | Changing the thresholds |
| Install name `rai-governance-platform` version string 1.3.1 | Yes as source metadata | `pyproject.toml` | Equating that string with git tag `v1.3.1` or with a new publish |
| DCO required except two historical SHAs | Yes | `dco.yml` and `tests/test_dco_historical_exception.py` | Adding a third exception |
| Staging is provisioned | No | No apply | Any status page saying operational |
| Production is launched | No | No deploy | Global announcement |
| SOC 2, ISO, or similar certification | No | Not in this review | Badges |
| Named customers or design partners | No | Not supplied | Logos |
| Uptime SLO | No | Proposal only in Phase 6 | 99.9% on the site |
| Local `whitepact-mcp` stdio is governed or tenant-protected | No | `docs/launch/LOCAL_STDIO_MCP_SCOPE.md` | Calling community stdio a control, a firewall, or protected execution |

## Supported integrations the docs already name

MCP, the Python SDK, and optional extras for dashboard, postgres, redis, telemetry, and agent frameworks are extras of `rai-governance-platform`. Each extra is supported only to the extent its tests and docs say. This pass did not re-test every extra.

## Security reporting

Use the process in `SECURITY.md`. Do not publish a new disclosure from this branch.

## Gate

CONDITIONAL. The register is a constraint on public copy, not permission to publish.
