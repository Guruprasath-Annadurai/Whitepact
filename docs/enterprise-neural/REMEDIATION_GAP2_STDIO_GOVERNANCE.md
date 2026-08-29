# Security Remediation Gap 2 — Stdio MCP Governance Bypass: Design + Report

**Superseded in part by Heart Enforcement Chokepoint Closure, Phase
E2** (see `docs/heart-production-closure/ENFORCEMENT_PATH_MATRIX.md`):
this document's original decision let `enterprise_mode=true` stdio
keep executing MINIMAL/LOW risk-tier tools with zero governance check.
The Phase E0 audit named that itself a real bypass -- `enterprise_mode`
is this codebase's "production authority-enforced mode" flag, and
stdio structurally cannot satisfy a Heart legitimacy check at any risk
tier (no organizational identity exists to check it against). As of
that closure work, `enterprise_mode=true` blocks ALL stdio tool
execution, not just non-MINIMAL/LOW. The risk-tier analysis and
architecture reasoning below remain accurate history for how the
original, now-tightened decision was reached; the error code changed
from `stdio_privileged_execution_blocked` to
`stdio_execution_blocked_in_enterprise_mode` to reflect the new,
unconditional behavior.

## Reproduction

Confirmed, not assumed: `mcp/server.py::_call_tool()` is the single
handler both transports (hosted HTTP/SSE and self-hosted stdio) share.
`_current_org`/`_current_governance` are `ContextVar`s populated only
by the hosted-HTTP transport's auth middleware per connection — on
stdio, both are always `None`. Reading the function's control flow
directly: when `ctx is None` (stdio), every gate (plan/quota checking,
`apply_governance()`) is skipped by its own `if ctx is not None`/`if
governance is not None and ctx is not None` conditions, and execution
falls straight through to `result = await dispatch_tool(name,
call_arguments)` with **zero** authority, risk, or policy check of any
kind. `"self-hosted"` is a stated design assumption (the trust
boundary is the local OS process/user), not itself a security
justification, per the remediation directive's own instruction — this
document does not accept that phrase as a substitute for analysis.

## Complete tool inventory, by risk tier

`governance/risk.py`'s `TOOL_RISK_TIERS` (already drift-tested against
the live tool list, `tests/test_governance_risk.py`) covers all 30 of
this platform's tools with no gap:

| Tier | Count | Tools |
|---|---|---|
| MINIMAL (→ **LOW RISK**) | 3 | `rai_health`, `rai_audit_summary`, `rai_org_status` |
| LOW (→ **LOW RISK**) | 12 | `rai_scan`, `rai_pii_report`, `rai_policy_check`, `rai_stream_scan`, `rai_memory_write_check`, `rai_memory_read_check`, `rai_causal_influence_check`, `rai_trust_score`, `rai_check_trust`, `rai_cost_estimate`, `rai_budget_check`, `rai_model_route` |
| MEDIUM (→ **MODERATE/PRIVILEGED**) | 7 | `rai_compliance`, `rai_eu_ai_act_classify`, `rai_iso42001_gap`, `rai_incident_log`, `rai_passport_generate`, `rai_executive_summary`, `rai_webhook_status` |
| HIGH (→ **SECURITY CRITICAL**) | 8 | `rai_hallucination`, `rai_bias_evaluate`, `rai_drift_check`, `rai_redteam_payloads`, `rai_redteam_analyze`, `rai_compare_models`, `rai_benchmark`, `rai_benchmark_prompts` |

## Architecture decision

**Option A** (route stdio through the full Authority → Brain →
Citadel → ExecutionPermit pipeline) is rejected for this pass: stdio
has no organizational/session identity at all — building one would
mean inventing an auto-provisioned or config-declared org identity for
the local operator, a materially larger architectural decision this
remediation pass is not authorized to make unilaterally (it changes
what "self-hosted" means for every existing deployment, not just adds
a check).

**Chosen: Option C, layered with Option B's opt-in gate.** Reuses
Gap 1's `Settings.enterprise_mode` flag (deliberately, not a second
"enterprise" concept) rather than duplicating it:

- `enterprise_mode=false` (default): stdio behavior is **completely
  unchanged** — every tool remains callable, exactly as today. This
  preserves the existing, honest "self-hosted = local trust boundary"
  posture for development/self-hosted use, which the directive does
  not ask this pass to eliminate, only to stop treating as sufficient
  justification for enterprise deployments.
- `enterprise_mode=true`: stdio may only execute tools classified
  `RiskTier.MINIMAL` or `RiskTier.LOW` — the explicit,
  already-classified "local development-only capability set" the
  directive's Option C asks for, reusing the existing risk taxonomy
  rather than inventing a new one. `MEDIUM`/`HIGH`-tier tools (and any
  future tool `classify_action_risk()` would default to `MEDIUM` for
  — fail-closed, per the platform's own existing "unclassified is not
  the same claim as verified-safe" rule) are denied with an explicit
  `stdio_privileged_execution_blocked` error, never silently allowed
  or silently no-op'd.

This satisfies "**UNKNOWN = DENY**" from the constitution directly:
an unrecognized tool name defaults to `RiskTier.MEDIUM` via the
existing `classify_action_risk()`, which this gate blocks in
enterprise mode — a brand-new tool added without updating the risk
table is blocked by default in enterprise mode, not silently allowed.

## Implementation

`mcp/server.py::_call_tool()` — one new check, immediately before the
existing final `dispatch_tool()` fallback, only reached when `ctx is
None` (i.e. genuinely stdio; a hosted request always has `ctx` set by
its own auth middleware before reaching this point):

```python
if ctx is None:
    from responsibleai.dashboard.config import get_settings
    from responsibleai.governance.risk import RiskTier, classify_action_risk

    if get_settings().enterprise_mode:
        risk_tier = classify_action_risk("mcp_tool_call", name)
        if risk_tier not in (RiskTier.MINIMAL, RiskTier.LOW):
            return _text_and_structured({
                "error": "stdio_privileged_execution_blocked",
                "message": (...),
            })
```

Local imports match this file's own established convention (keep the
stdio import graph free of anything not needed when a feature is
off).

## What this does not do — named explicitly

- Does not give stdio any authority/organization/session identity.
  "Cross-tenant", "revoked authority", "stale authority", "missing org
  identity" scenarios the directive's own test list names do not apply
  to stdio's actual architecture (it never had any identity to begin
  with) — fabricating one to make those specific tests pass would
  itself be dishonest. What *is* real and tested: privileged execution
  is blocked in enterprise mode regardless of any identity concept.
- Does not change hosted-HTTP behavior at all — this gate only ever
  triggers when `ctx is None`.
- Does not add per-tool argument validation, mutation detection, or
  target substitution checks to stdio — those remain real, unaddressed
  gaps (mirroring the hosted-governed path's own named gap: no
  LLM-tool-argument schema validation, from Phase 8's audit) tracked
  separately, not silently assumed solved by this risk-tier gate.
