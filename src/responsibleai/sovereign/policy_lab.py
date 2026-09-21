# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Policy Lab — validate and test policy packs without mutating authority."""

from __future__ import annotations

from pydantic import BaseModel, Field

from responsibleai.governance.models import ActionRequest, AgentContext, IdentityContext
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.risk import RiskTier
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.zero_effect import zero_effect_operation


class PolicyTestCase(BaseModel):
    name: str
    action_type: str
    target: str = "policy-lab:target"
    risk_tier: str = "LOW"
    expect_effect: str | None = None


class PolicyTestResult(BaseModel):
    name: str
    matched_rule_id: str | None
    observed_effect: str | None
    passed: bool
    explanation: str


class PolicyLabReport(BaseModel):
    organization_id: str
    policy_version: int
    results: list[PolicyTestResult] = Field(default_factory=list)


@zero_effect_operation
async def run_policy_tests(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    cases: list[PolicyTestCase],
) -> PolicyLabReport:
    policy = await store.policies.get_policy(ctx.organization_id)
    identity = IdentityContext(identity_id="policy-lab", kind="agent", org_id=ctx.organization_id)
    agent = AgentContext(
        identity=identity, organization_id=ctx.organization_id, agent_id="policy-lab"
    )
    results: list[PolicyTestResult] = []
    for case in cases:
        action = ActionRequest(
            agent=agent,
            action_type=case.action_type,
            target=case.target,
            arguments={},
            purpose="policy-lab",
        )
        tier = RiskTier(case.risk_tier) if case.risk_tier in RiskTier.__members__ else RiskTier.LOW
        match = policy.evaluate(action, tier)
        observed = match.rule.effect.value if match else None
        passed = case.expect_effect is None or observed == case.expect_effect
        results.append(
            PolicyTestResult(
                name=case.name,
                matched_rule_id=match.rule.rule_id if match else None,
                observed_effect=observed,
                passed=passed,
                explanation="Evaluated via Policy.evaluate — not hardcoded",
            )
        )
    return PolicyLabReport(
        organization_id=ctx.organization_id,
        policy_version=policy.version,
        results=results,
    )


def validate_policy_rules(rules: list[PolicyRule]) -> list[str]:
    """Lint policy rules for structural validity (pure, no I/O)."""
    errors: list[str] = []
    seen: set[str] = set()
    for rule in rules:
        if rule.rule_id in seen:
            errors.append(f"duplicate rule_id {rule.rule_id}")
        seen.add(rule.rule_id)
        if not rule.reason_code.strip():
            errors.append(f"rule {rule.rule_id} missing reason_code")
    return errors


class PolicyDiffEntry(BaseModel):
    rule_id: str
    change: str  # added | removed | unchanged
    baseline_effect: str | None = None
    candidate_effect: str | None = None


class PolicyDiffReport(BaseModel):
    organization_id: str
    baseline_version: int
    candidate_rule_count: int
    entries: list[PolicyDiffEntry] = Field(default_factory=list)


class PolicyScenarioResult(BaseModel):
    action_type: str
    baseline_effect: str | None
    candidate_effect: str | None
    decision_changed: bool


class PolicySimulateReport(BaseModel):
    organization_id: str
    scenarios: list[PolicyScenarioResult] = Field(default_factory=list)


@zero_effect_operation
async def diff_policy_candidate(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    candidate_rules: list[PolicyRule],
) -> PolicyDiffReport:
    policy = await store.policies.get_policy(ctx.organization_id)
    baseline = {r.rule_id: r for r in policy.rules}
    candidate = {r.rule_id: r for r in candidate_rules}
    entries: list[PolicyDiffEntry] = []
    for rule_id, rule in baseline.items():
        if rule_id not in candidate:
            entries.append(
                PolicyDiffEntry(
                    rule_id=rule_id,
                    change="removed",
                    baseline_effect=rule.effect.value,
                )
            )
        else:
            cand = candidate[rule_id]
            entries.append(
                PolicyDiffEntry(
                    rule_id=rule_id,
                    change="unchanged" if cand.effect == rule.effect else "modified",
                    baseline_effect=rule.effect.value,
                    candidate_effect=cand.effect.value,
                )
            )
    for rule_id, rule in candidate.items():
        if rule_id not in baseline:
            entries.append(
                PolicyDiffEntry(
                    rule_id=rule_id,
                    change="added",
                    candidate_effect=rule.effect.value,
                )
            )
    return PolicyDiffReport(
        organization_id=ctx.organization_id,
        baseline_version=policy.version,
        candidate_rule_count=len(candidate_rules),
        entries=entries,
    )


@zero_effect_operation
async def simulate_policy_candidate(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    *,
    candidate_rules: list[PolicyRule],
    action_types: list[str],
) -> PolicySimulateReport:
    from responsibleai.governance.policy import Policy

    baseline = await store.policies.get_policy(ctx.organization_id)
    candidate = Policy(
        org_id=ctx.organization_id,
        rules=list(candidate_rules),
        version=baseline.version,
    )
    identity = IdentityContext(identity_id="policy-lab", kind="agent", org_id=ctx.organization_id)
    agent = AgentContext(
        identity=identity, organization_id=ctx.organization_id, agent_id="policy-lab"
    )
    scenarios: list[PolicyScenarioResult] = []
    for action_type in action_types:
        action = ActionRequest(
            agent=agent,
            action_type=action_type,
            target="policy-lab:target",
            arguments={},
            purpose="policy-lab-simulate",
        )
        b = baseline.evaluate(action, RiskTier.LOW)
        c = candidate.evaluate(action, RiskTier.LOW)
        be = b.rule.effect.value if b else None
        ce = c.rule.effect.value if c else None
        scenarios.append(
            PolicyScenarioResult(
                action_type=action_type,
                baseline_effect=be,
                candidate_effect=ce,
                decision_changed=be != ce,
            )
        )
    return PolicySimulateReport(organization_id=ctx.organization_id, scenarios=scenarios)
