# Phase 9 — Production go / no-go framework

**Current automated decision: NO-GO.**

The checker is `scripts/release_evidence_check.py`. It reports four separate results:

1. `packet_completeness` — every gate is present and bound to the candidate head, tree, environment, and, where required, an `https` artifact plus `sha256:` digest. Placeholder hosts and placeholder text are incomplete.
2. `independent_verification` — always `UNVERIFIED` in this process. It does not fetch URLs or trust a status string.
3. `owner_approval` — always `NOT_AUTHORIZED`. A JSON claim is not an owner signature.
4. `production_authorization` — always `NO-GO`.

A complete packet still cannot produce a production GO. `conditional_scope` in the packet does not authorize a limited launch. Caller-supplied `decision`, `production_authorization`, `independent_verification`, and `owner_approval` fields are ignored. `http`, `file`, `localhost`, and `127.0.0.1` artifact pointers are incomplete.

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

Observed before the trust-boundary change: exit code 1 and `decision` `NO-GO`. After that change the same packet stays `NO-GO`, and a fully shaped untrusted packet is also `NO-GO` with `independent_verification` `UNVERIFIED` and `owner_approval` `NOT_AUTHORIZED`.

That CI acceptance does not include the successor's memory-scope fix or the action-pin fix. Do not mark `ci.canonical` accepted for the successor until a new run exists.

## Decision rules

- **Packet completeness.** Structural only. A placeholder URL, a missing digest, or a head/tree mismatch is incomplete.
- **Independent verification.** Not performed by this script. The required procedure is in the command's `verifier_procedure` field.
- **Owner approval.** Not granted by this script.
- **Production authorization.** `NO-GO` from this script, including when the packet is complete and includes `conditional_scope`.

A local PASS is not a live staging PASS. A URL in the packet is not an authenticated artifact.

## Gate

The framework is implemented. The release decision is **NO-GO**.
