# Phase 9 — Production go / no-go framework

**Current automated decision: NO-GO.**

The checker is `scripts/release_evidence_check.py`. It returns `GO` only when every mandatory gate has an accepted evidence record of the required kind. A local log cannot satisfy a live, independent, or owner gate. `CONDITIONAL_GO` is returned only when the caller sets a non-empty `conditional_scope` and there are zero failures. It is not inferred from a partial packet.

## Gates

| Gate | Required kind | Live artifact required |
|------|----------------|------------------------|
| `runtime.authority` | `local_test` | No |
| `tenant.isolation` | `local_test` | No |
| `grant.replay` | `local_test` | No |
| `ci.canonical` | `github_actions` | Yes |
| `independent.qualification` | `independent_audit` | Yes |
| `staging.live` | `live_staging` | Yes |
| `backup.restore.live` | `live_staging` | Yes |
| `cloud.security.live` | `live_staging` | Yes |
| `owner.infrastructure` | `owner_approval` | Yes |
| `owner.commercial` | `owner_approval` | Yes |
| `owner.legal` | `owner_approval` | Yes |
| `public.launch` | `owner_approval` | Yes |

## Packet evaluated

`docs/launch/evidence/rc-0cdef394.json` records only:

- `ci.canonical` accepted
- artifact `https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/37900487645`
- SHA `0cdef3947503adf7c3f08a5116a4808deda1d3f7`

Command:

```bash
python scripts/release_evidence_check.py docs/launch/evidence/rc-0cdef394.json
```

Observed: exit code 1, `decision` `NO-GO`, `accepted` contains only `ci.canonical`.

That CI acceptance does not include the successor's memory-scope fix or the action-pin fix. Do not mark `ci.canonical` accepted for the successor until a new run exists.

## Decision rules

- **GO.** Every mandatory gate accepted with the right kind and, where required, an artifact pointer. Not available now.
- **CONDITIONAL GO.** Same completeness, plus an explicit scope string such as one design partner and a named tool allowlist. Not available now. A scope string with missing gates stays `NO-GO` (`tests/test_release_evidence_check.py`).
- **NO-GO.** Any mandatory gate missing, mistyped, or without its artifact. This is the current result.

A local PASS is not a live staging PASS. The checker encodes that by kind, not by a comment.

## Gate

The framework is implemented. The release decision is **NO-GO**.
