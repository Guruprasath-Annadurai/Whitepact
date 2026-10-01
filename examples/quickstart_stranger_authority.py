# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical stranger quickstart — production authority + execution path.

Exercises the same components the hosted MCP / dashboard governed-tool path uses:

  OrgContext → GovernanceContext → AuthorityResolver (root + consent + delegation)
  → WhitePactRuntimeGateway → authorize_execution → InternalToolExecutor

Run from repository root:

    python examples/quickstart_stranger_authority.py

No API keys, Docker, or network required.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, "src")

from responsibleai.db import (
    ApprovalRepository,
    DelegationRepository,
    EvidenceRepository,
    OrgRepository,
    PolicyRepository,
    create_engine,
)
from responsibleai.db.consent_proof_repository import ConsentProofRepository
from responsibleai.db.execution_nonce_repository import ExecutionNonceRepository
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.db.root_authority_repository import RootAuthorityRepository
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.authority_resolver import AuthorityResolver
from responsibleai.governance.consent_proof import ConsentMethod, build_consent_proof
from responsibleai.governance.root_authority import RootType, build_root_authority_record
from responsibleai.integrations.client import TrustClient
from responsibleai.mcp.governance_integration import GovernanceServices, apply_governance
from responsibleai.rbac.models import OrgContext, Plan, Role

TOOL = "rai_health"
PURPOSE = "stranger-quickstart"
ORG_SLUG = "stranger-quickstart-co"


async def _seed_runtime_authority(
    engine,
    *,
    organization_id: str,
    principal_id: str,
) -> None:
    """Mirror tests/conftest.py seed_runtime_authority (explicit root + consent + delegation)."""
    owner = f"test-owner:{organization_id}"
    expires = datetime.now(UTC) + timedelta(hours=1)
    root = build_root_authority_record(
        owner,
        RootType.HUMAN,
        "whitepact-quickstart",
        "stranger-quickstart-fixture",
        organization_id=organization_id,
        evidence_refs=("quickstart-root-evidence",),
        expires_at=expires,
    )
    await RootAuthorityRepository(engine).create(root)
    consent = build_consent_proof(
        owner,
        root.root_id,
        principal_id,
        "quickstart governed tool scope",
        PURPOSE,
        ConsentMethod.EXPLICIT_UI_ACTION,
        allowed_action_types=(TOOL,),
        allowed_targets=(TOOL,),
        evidence_refs=("quickstart-consent-evidence",),
        expires_at=expires,
    )
    await ConsentProofRepository(engine).create(consent, organization_id=organization_id)
    await DelegationRepository(engine).grant(
        organization_id,
        principal_id,
        granted_action_types=frozenset({TOOL}),
        constraints={"allowed_targets": [TOOL]},
        purpose=PURPOSE,
        granted_by=owner,
        expires_at=expires,
    )


def _services(engine) -> GovernanceServices:
    delegations = DelegationRepository(engine)
    return GovernanceServices(
        gateway=WhitePactRuntimeGateway(),
        evidence_repo=EvidenceRepository(engine),
        approval_repo=ApprovalRepository(engine),
        policy_repo=PolicyRepository(engine),
        trust_client=TrustClient(),
        webhook_manager=None,
        ceiling_repo=None,
        workflow_rule_repo=None,
        delegation_repo=delegations,
        autonomy_budget_repo=None,
        outcome_repo=None,
        intent_repo=None,
        nonce_repo=ExecutionNonceRepository(engine),
        epoch_repo=RevocationEpochRepository(engine),
        authority_resolver=AuthorityResolver(
            RootAuthorityRepository(engine),
            ConsentProofRepository(engine),
            delegations,
        ),
        org_repo=OrgRepository(engine),
    )


async def _governed_call(services: GovernanceServices, ctx: OrgContext) -> dict:
    outcome = await apply_governance(TOOL, {}, ctx, services, purpose=PURPOSE)
    if outcome.proceed:
        assert outcome.result is not None
        return {"status": "executed", "result": outcome.result}
    assert outcome.blocked_response is not None
    return outcome.blocked_response


async def main() -> None:
    print("WhitePact canonical stranger quickstart\n")

    engine = create_engine(":memory:")
    await engine.init()

    org_repo = OrgRepository(engine)
    org = await org_repo.create_org("Stranger Quickstart Co", ORG_SLUG, plan=Plan.ENTERPRISE)
    _key_rec, _raw_key = await org_repo.create_key(org.id, "quickstart-key", role=Role.ANALYST)
    principal_id = _key_rec.id

    await _seed_runtime_authority(
        engine,
        organization_id=org.id,
        principal_id=principal_id,
    )

    ctx = OrgContext(
        key_id=principal_id,
        role=Role.ANALYST,
        org_id=org.id,
        org_name=org.name,
        plan=Plan.ENTERPRISE,
        authentication_method="api_key",
    )
    services = _services(engine)
    evidence_repo = EvidenceRepository(engine)
    delegations = DelegationRepository(engine)

    print("[1] Fresh AuthorityResolver + apply_governance → tool executes")
    before = await _governed_call(services, ctx)
    assert before["status"] == "executed"
    allow_rows = await evidence_repo.list_for_org(org.id, decision="ALLOW")
    assert any(r.action_type == TOOL for r in allow_rows)
    print(f"    executed rai_health; ALLOW evidence rows={len(allow_rows)}")

    print("\n[2] Revoke persisted delegation for the API key principal")
    revoked = await delegations.revoke_branch(
        org.id, principal_id, revoked_by=f"test-owner:{org.id}", reason="quickstart revoke"
    )
    print(f"    revoked_delegation_ids={revoked}")

    print("\n[3] Fresh resolution after revoke → DENY, tool NOT executed again")
    after = await _governed_call(services, ctx)
    assert after.get("error") == "governance_denied"
    deny_rows = await evidence_repo.list_for_org(org.id, decision="DENY")
    assert any(r.action_type == TOOL for r in deny_rows)
    print(f"    blocked: {after.get('reason_codes', [])[:2]}")

    print("\n--- Why callers must never cache authority ---")
    print(
        "WhitePactRuntimeGateway.evaluate() alone trusts the AuthorityContext you pass in.\n"
        "Production paths call AuthorityResolver + delegation freshness checks on every request.\n"
        "Demonstration (educational only — NOT production behavior):"
    )
    stale = AuthorityContext(
        delegated_by=f"test-owner:{org.id}",
        granted_action_types=frozenset({TOOL}),
        constraints={"allowed_targets": [TOOL]},
    )
    agent = AgentContext(
        identity=IdentityContext(principal_id, "api_key", org_id=org.id),
        agent_id=principal_id,
        framework="quickstart",
    )
    action = ActionRequest(agent=agent, action_type=TOOL, target=TOOL, purpose=PURPOSE)
    stale_decision = WhitePactRuntimeGateway().evaluate(action, stale)
    print(
        f"    gateway.evaluate() with stale in-memory context → {stale_decision.decision.value}\n"
        "    (apply_governance above correctly denied after revoke.)"
    )
    assert stale_decision.decision == GovernanceDecision.ALLOW

    await engine.close()
    print("\nQuickstart complete. See docs/quickstart.md and docs/examples/http_governance.md")


if __name__ == "__main__":
    asyncio.run(main())
