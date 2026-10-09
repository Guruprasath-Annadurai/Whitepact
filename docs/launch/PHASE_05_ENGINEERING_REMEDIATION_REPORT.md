# Phase 5 — Engineering remediation report

## WP-LAUNCH-P1-MEMORY-SCOPE-01

**Impact.** A delegated agent could receive a wider memory namespace than the delegating authority held. That is an authority expansion on a consequential path. Human approval and the gateway's other checks did not see this field at attenuation time.

**Reproduction before the fix.** Build two `AuthorityContext` values with the same action types. Parent constraint `memory_scope=org:acme`. Child constraint `memory_scope=org`. `validate_attenuation(parent, child)` returned `None` on `0cdef394`.

**Fix.** `validate_attenuation` in `src/responsibleai/governance/models.py` now requires a string child scope that is equal to the parent scope or a descendant (`child == parent` or `child.startswith(parent + ":")`). A missing or non-string child scope fails closed. An unconstrained parent may still let the child narrow itself. The gateway already calls `validate_attenuation` when `parent_authority` is set, so the deny is on the evaluate path.

**Tests.**

- `tests/test_authority_attenuation.py::TestMemoryScopeEscalation`
- `tests/test_governance_core.py::TestGatewayAttenuation::test_widened_memory_scope_denied_before_execution`
- `tests/test_governance_core.py::TestGatewayAttenuation::test_descendant_memory_scope_is_not_escalation`
- Hypothesis properties in `tests/test_property_based.py::TestAttenuationProperties`

**Not changed.** Coverage thresholds, policy semantics other than this missing comparison, website source, and historical commits.

## WP-LAUNCH-P2-ACTION-PIN-01

**Impact.** `scripts/check_pinned_actions.py` matched only a line that starts with `uses:`. A step written as `- uses: actions/checkout@v4` was invisible. `.github/workflows/deploy-staging-manual.yml` used that form twice. OpenSSF policy checks on `0cdef394` reported the pin script clean while those lines were present.

**Fix.** The regular expression accepts an optional YAML list dash. Both staging checkout steps now use `actions/checkout@11d5960a326750d5838078e36cf38b85af677262`, the same commit already used by `ci.yml` and `dco.yml`. `tests/test_pinned_actions.py` fails if the dash form regresses, and it scans every workflow in the tree.

**Security effect.** The staging workflow still does not apply infrastructure. The pin removes a movable tag from a workflow that will run after owner approval.

## Evidence

Local pytest of the governance, DCO, and evidence slice: 61 passed. Follow-up of pin tests, memory-scope class, and evidence checker: 20 passed. Commands are in `PHASE_02_ANTIGRAVITY_INDEPENDENT_AUDIT_HANDOFF.md`.

Independent retest is still required. Status in `docs/enterprise/M6_DEFECT_REGISTER.md`: `ENGINEERING_FIXED — INDEPENDENT RETEST REQUIRED`.
