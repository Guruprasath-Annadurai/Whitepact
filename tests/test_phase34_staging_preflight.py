# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Phase 3/4 staging preflight. Offline success is not live acceptance."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from responsibleai.governance.execution import (
    AuthorizationAlreadyConsumedError,
    AuthorizationExpiredError,
    AuthorizationOrganizationMismatchError,
    DecisionNotExecutableError,
    admit_execution,
    authorize_execution,
)
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.isolation.environment import build_isolated_environment
from responsibleai.ops.isolated_restore import rehearsal_passes, rehearse_isolated_restore
from responsibleai.ops.staging_cost import (
    STAGING_CEILING_CENTS,
    assess_spend,
    cost_controls,
    optional_backup_eur,
    staging_monthly_cents,
)
from responsibleai.ops.staging_rollout import (
    OWNER_GATE_TOKEN,
    StagingRolloutRefused,
    plan_deploy,
    plan_health,
    plan_rollback,
)
from responsibleai.ops.staging_scope import (
    StagingAcceptanceRefused,
    claim_staging_acceptance,
    offline_record,
)
from responsibleai.ops.staging_secrets import review_staging_secrets
from responsibleai.ops.staging_static import (
    OWNER_DEPENDENCIES,
    PR_171_SHA,
    PR_172_HEAD_IS_ANCESTOR,
    PR_172_HEAD_SHA,
    PREFLIGHT_BASE_SHA,
    PREFLIGHT_BASE_TREE,
    isolation_defects,
    nat_cross_tier_forward,
    nat_source_separation_violations,
)

ROOT = Path(__file__).resolve().parents[1]


def _action(org_id: str = "org-a") -> ActionRequest:
    return ActionRequest(
        agent=AgentContext(
            identity=IdentityContext(identity_id="agent-1", kind="api_key", org_id=org_id),
            organization_id=org_id,
        ),
        action_type="governed_tool",
        target="mcp::staging-offline",
        arguments={"query": "status"},
    )


def test_static_isolation_defects_are_closed() -> None:
    assert isolation_defects() == ()


def test_staging_cost_is_the_approved_ceiling() -> None:
    assert staging_monthly_cents() == STAGING_CEILING_CENTS == 3595
    alert = assess_spend(3595)
    assert alert.severity == "at_ceiling"
    assert alert.blocks_apply is False
    assert "backups" in alert.action
    critical = assess_spend(3596)
    assert critical.severity == "critical"
    assert critical.blocks_apply is True
    assert optional_backup_eur() == "5.592"
    controls = cost_controls()
    assert controls["kind"] == "terraform_price_book_ceiling"
    assert controls["is_billing_alert"] is False
    assert controls["billing_alert_configured"] is False
    assert controls["includes_vat"] is False
    assert controls["includes_backups"] is False
    assert controls["hypothetical_de_gross_eur"] == "42.7805"
    assert controls["ceiling_cents"] == 3595
    server_cents = 849 + 849 + 549 + 549
    terraform_backup_cents = ((server_cents * 20) + 99) // 100
    assert terraform_backup_cents == 560
    assert STAGING_CEILING_CENTS + terraform_backup_cents > STAGING_CEILING_CENTS


def test_secret_review_does_not_echo_values() -> None:
    secret = "supersecretvalue-not-for-logs"
    checks = review_staging_secrets({"HCLOUD_TOKEN": secret, "R2_BUCKET": "REPLACE_BEFORE_APPLY"})
    rendered = json.dumps([{"name": item.name, "status": item.status} for item in checks])
    assert secret not in rendered
    by_name = {item.name: item.status for item in checks}
    assert by_name["HCLOUD_TOKEN"] == "present"
    assert by_name["R2_BUCKET"] == "placeholder"
    assert by_name["POSTGRES_PASSWORD"] == "missing"
    assert by_name["WHITEPACT_EXECUTION_DB_PASSWORD"] == "missing"
    reused = "authority-owner-secret-value"
    distinct = review_staging_secrets(
        {"POSTGRES_PASSWORD": reused, "WHITEPACT_EXECUTION_DB_PASSWORD": reused + "-exec"}
    )
    reused_checks = review_staging_secrets(
        {"POSTGRES_PASSWORD": reused, "WHITEPACT_EXECUTION_DB_PASSWORD": reused}
    )
    reused_rendered = json.dumps([item.status for item in reused_checks])
    assert reused not in reused_rendered
    assert {item.name: item.status for item in reused_checks}[
        "WHITEPACT_EXECUTION_DB_PASSWORD"
    ] == ("reused_authority_owner")
    assert {item.name: item.status for item in distinct}[
        "WHITEPACT_EXECUTION_DB_PASSWORD"
    ] == "present"


def test_rollout_plan_has_no_apply_and_refuses_production_health() -> None:
    plan = plan_deploy("a" * 40, OWNER_GATE_TOKEN)
    assert plan["terraform_apply"] is False
    assert plan["dns_change"] is False
    assert plan["production"] is False
    assert all("apply" not in str(command) for command in plan["commands"])
    with pytest.raises(StagingRolloutRefused):
        plan_deploy("a" * 40, "approve")
    assert plan_health(None)["status"] == "NOT_RUN"
    with pytest.raises(StagingRolloutRefused):
        plan_health("https://whitepact.com/livez")
    rollback = plan_rollback("b" * 40, "c" * 40)
    assert rollback["execute"] is False
    assert "DROP" not in " ".join(rollback["steps"]).upper() or "Do not drop" in " ".join(
        rollback["steps"]
    )


def test_offline_record_cannot_claim_staging_acceptance() -> None:
    record = offline_record("customer", passed=True)
    assert record.scope == "offline"
    assert record.live_staging_accepted is False
    with pytest.raises(StagingAcceptanceRefused):
        claim_staging_acceptance(record)


def test_governed_mcp_and_tenant_isolation_offline(tmp_path: Path) -> None:
    action = _action("org-a")
    deny = DecisionResult(
        decision=GovernanceDecision.DENY, action_id=action.action_id, reason_codes=["NO_GRANT"]
    )
    with pytest.raises(DecisionNotExecutableError):
        authorize_execution(deny, action)
    allow = DecisionResult(
        decision=GovernanceDecision.ALLOW, action_id=action.action_id, reason_codes=["GRANT"]
    )
    permit = authorize_execution(allow, action, ttl_seconds=60)
    import asyncio

    asyncio.run(admit_execution(permit, action, None))
    with pytest.raises(AuthorizationAlreadyConsumedError):
        asyncio.run(admit_execution(permit, action, None))
    expired = authorize_execution(allow, action, ttl_seconds=60)
    expired.expires_at = datetime.now(UTC) - timedelta(seconds=5)
    with pytest.raises(AuthorizationExpiredError):
        asyncio.run(admit_execution(expired, action, None))
    fresh = authorize_execution(allow, action, ttl_seconds=60)
    with pytest.raises(AuthorizationOrganizationMismatchError):
        asyncio.run(admit_execution(fresh, _action("org-b"), None))
    env = build_isolated_environment(
        organization_id="org-a",
        action_id=action.action_id,
        extra_env={"POSTGRES_PASSWORD": "nope", "SAFE_FLAG": "1"},
    )
    assert "POSTGRES_PASSWORD" not in env
    assert env["WHITEPACT_TENANT_ID"] == "org-a"
    backend = (ROOT / "src/responsibleai/isolation/container_backend.py").read_text(
        encoding="utf-8"
    )
    assert "--network=none" in backend
    assert "docker.sock" not in backend
    rehearsal = rehearse_isolated_restore(tmp_path, secret="offline-restore-secret")
    assert rehearsal_passes(rehearsal)
    record = offline_record("governed-mcp-and-restore", passed=True)
    with pytest.raises(StagingAcceptanceRefused):
        claim_staging_acceptance(record)


def test_offline_load_rehearsal_stays_offline() -> None:
    action = _action()
    decision = DecisionResult(
        decision=GovernanceDecision.ALLOW, action_id=action.action_id, reason_codes=["LOAD"]
    )
    samples: list[float] = []
    for _ in range(50):
        started = time.perf_counter()
        authorize_execution(decision, action, ttl_seconds=30)
        samples.append(time.perf_counter() - started)
    samples.sort()
    p95 = samples[int(len(samples) * 0.95) - 1]
    assert p95 < 0.05
    record = offline_record("load", passed=True)
    assert record.live_staging_accepted is False


def test_nat_forwarding_rejects_cross_tier_sources() -> None:
    locals_text = (
        ROOT / "infra/terraform/modules/whitepact-hetzner-foundation/locals.tf"
    ).read_text(encoding="utf-8")
    assert nat_source_separation_violations(locals_text) == ()
    hostile = (
        ("var.saas_subnet_cidr", "var.authority_egress_cidrs"),
        ("var.saas_subnet_cidr", "var.execution_egress_cidrs"),
        ("var.authority_subnet_cidr", "var.saas_egress_cidrs"),
        ("var.authority_subnet_cidr", "var.execution_egress_cidrs"),
        ("var.execution_subnet_cidr", "var.saas_egress_cidrs"),
        ("var.execution_subnet_cidr", "var.authority_egress_cidrs"),
        ("var.mgmt_subnet_cidr", "var.saas_egress_cidrs"),
        ("var.mgmt_subnet_cidr", "var.authority_egress_cidrs"),
        ("var.mgmt_subnet_cidr", "var.execution_egress_cidrs"),
    )
    for source_var, dest_var in hostile:
        assert nat_cross_tier_forward(locals_text, source_var, dest_var) is False
    assert nat_cross_tier_forward(locals_text, "var.saas_subnet_cidr", "var.saas_egress_cidrs")
    assert nat_cross_tier_forward(
        locals_text, "var.authority_subnet_cidr", "var.authority_egress_cidrs"
    )
    assert nat_cross_tier_forward(
        locals_text, "var.execution_subnet_cidr", "var.execution_egress_cidrs"
    )
    stolen = (
        'nat_forward_rules = join("\\n", concat(\n'
        "  [\n"
        '    "ip saddr { ${var.saas_subnet_cidr} } ip daddr { ${var.authority_egress_cidrs} } '
        'tcp dport 443 accept comment \\"stolen\\"",\n'
        '    "ip daddr { ${var.saas_egress_cidrs} } tcp dport 443 accept comment \\"open\\"",\n'
        "  ],\n"
        "))\n"
        "}\n"
    )
    violations = nat_source_separation_violations(stolen)
    assert any("SaaS source can reach authority destinations." in item for item in violations)
    assert any("no source restriction" in item for item in violations)


def test_cost_ceiling_is_not_a_billing_alert() -> None:
    foundation = ROOT / "infra/terraform/modules/whitepact-hetzner-foundation"
    cost = (foundation / "cost.tf").read_text(encoding="utf-8")
    variables = (foundation / "variables.tf").read_text(encoding="utf-8")
    staging = (ROOT / "infra/terraform/environments/staging/main.tf").read_text(encoding="utf-8")
    module_text = "\n".join(path.read_text(encoding="utf-8") for path in foundation.glob("*.tf"))
    assert "not a Hetzner billing alert" in cost
    assert "enable_server_backups" in variables
    assert "enable_server_backups = true" not in staging
    assert 'resource "hcloud_' in module_text
    assert "hcloud_budget" not in module_text
    assert "billing_alert" not in module_text.replace("is_billing_alert", "").replace(
        "billing_alert_configured", ""
    )


def test_preflight_branch_base_is_recorded() -> None:
    doc = (ROOT / "docs/launch/PHASE_03_04_FINAL_STAGING_PREFLIGHT.md").read_text(encoding="utf-8")
    assert PREFLIGHT_BASE_SHA in doc
    assert PREFLIGHT_BASE_TREE in doc
    assert PR_172_HEAD_SHA in doc
    assert PR_171_SHA in doc
    assert PR_172_HEAD_IS_ANCESTOR is False
    assert "not an ancestor" in doc


def test_owner_dependencies_are_listed_for_the_preflight_doc() -> None:
    ids = {item_id for item_id, _need in OWNER_DEPENDENCIES}
    assert "OWNER-GATE-1" in ids
    assert "HCLOUD_TOKEN" in ids
    assert "LIVE-ACCEPTANCE" in ids
    doc = (ROOT / "docs/launch/PHASE_03_04_FINAL_STAGING_PREFLIGHT.md").read_text(encoding="utf-8")
    for item_id, _need in OWNER_DEPENDENCIES:
        assert item_id in doc
    assert "35.95" in doc
    assert "6801d4ad" in doc
    assert "6fefece7" in doc


def test_offline_preflight_script() -> None:
    script = ROOT / "scripts/cloud/staging/preflight_offline.py"
    completed = subprocess.run(
        [os.environ.get("WHITEPACT_PYTHON", "python3"), str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["live_staging_accepted"] is False
    assert report["terraform_apply"] is False
    assert report["monthly_eur_ex_vat"] == "35.95"
    assert report["defects"] == []
    assert report["spend_alert"]["severity"] == "at_ceiling"
    assert report["spend_alert"]["is_billing_alert"] is False
    assert report["cost_controls"]["billing_alert_configured"] is False
    assert report["cost_controls"]["includes_vat"] is False
    assert report["cost_controls"]["includes_backups"] is False
    assert report["origin_client_certificate_enforced"] is False
    assert "cloudflare_aop_ca_bundle" in report["origin_artifacts_missing"]
    assert report["staging_provisioning"] == "NO-GO"
    assert report["ancestry"]["preflight_base_sha"] == PREFLIGHT_BASE_SHA
    assert report["ancestry"]["pr_172_head_is_ancestor"] is False


@pytest.mark.skipif(shutil.which("terraform") is None, reason="terraform CLI not installed")
def test_staging_and_foundation_validate() -> None:
    targets = [
        ROOT / "infra/terraform/modules/whitepact-hetzner-foundation",
        ROOT / "infra/terraform/environments/staging",
        ROOT / "infra/terraform/environments/development",
        ROOT / "infra/terraform/environments/production",
        ROOT / "infra/terraform/modules/cloudflare-edge",
    ]
    for target in targets:
        init = subprocess.run(
            ["terraform", "init", "-backend=false", "-input=false"],
            cwd=target,
            capture_output=True,
            text=True,
            check=False,
        )
        assert init.returncode == 0, init.stderr
        validate = subprocess.run(
            ["terraform", "validate"],
            cwd=target,
            capture_output=True,
            text=True,
            check=False,
        )
        assert validate.returncode == 0, validate.stderr
