# Phase 9 — Antigravity final audit packet

**Not an Antigravity result.**

## Identity

| Field | Value |
|-------|--------|
| Repository | https://github.com/Guruprasath-Annadurai/Whitepact |
| CI-green ancestor | `0cdef3947503adf7c3f08a5116a4808deda1d3f7` |
| CI run | https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/37900487645 |
| Successor branch | `cursor/whitepact-global-launch-execution-d20d` |
| Parent of the successor | `0cdef3947503adf7c3f08a5116a4808deda1d3f7` |
| Ecosystem tip not in the RC | `ae9e59057bdc69bd7681275db0daef7b815241e2` (PR #168) |
| `main` | `38f927229b4ea53d19a9107c78653307f5263629` |

Read `git rev-parse HEAD` and `git rev-parse HEAD^{tree}` on the successor after fetch. Reject the packet if those values are not the commits under review.

## Diff Antigravity should read

- `src/responsibleai/governance/models.py` — `memory_scope` attenuation
- `tests/test_authority_attenuation.py`
- `tests/test_governance_core.py`
- `tests/test_property_based.py`
- `scripts/check_pinned_actions.py`
- `tests/test_pinned_actions.py`
- `.github/workflows/deploy-staging-manual.yml` — checkout pin only
- `scripts/release_evidence_check.py`
- `tests/test_release_evidence_check.py`
- `docs/launch/evidence/rc-0cdef394.json`
- `docs/launch/PHASE_0*.md` and `PHASE_10_*.md`

## Commands

```bash
python -m pytest \
  tests/test_authority_attenuation.py \
  tests/test_governance_core.py::TestGatewayAttenuation \
  tests/test_property_based.py::TestAttenuationProperties \
  tests/test_pinned_actions.py \
  tests/test_release_evidence_check.py \
  tests/test_dco_historical_exception.py \
  -q --tb=short --override-ini='addopts='
python scripts/check_pinned_actions.py
python scripts/release_evidence_check.py docs/launch/evidence/rc-0cdef394.json
```

Expect the evidence command to exit 1 and print `NO-GO`.

## Questions that must stay fail-closed

1. Can a child `memory_scope` be wider than its parent? Must be no.
2. Does `- uses: actions/checkout@v4` fail the pin checker? Must be yes.
3. Does a local test file satisfy `staging.live`? Must be no.
4. Does CI green on `0cdef394` cover the successor? Must be no.

## Out of scope for a source audit

Live Hetzner, Cloudflare, DNS, payment, and production restore. Those stay NO-GO until separate evidence exists.

## Gate

Ready for independent review of the successor diff. Final production PASS is not available.
