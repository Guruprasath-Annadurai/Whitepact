# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Test-only seeder for Playwright governed-counter journeys."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from responsibleai.db import OrgRepository, PolicyRepository, create_engine
from responsibleai.db.consent_proof_repository import ConsentProofRepository
from responsibleai.db.delegation_repository import DelegationRepository
from responsibleai.db.root_authority_repository import RootAuthorityRepository
from responsibleai.governance.consent_proof import ConsentMethod, build_consent_proof
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.root_authority import RootType, build_root_authority_record
from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL


async def _seed(database_url: str, api_key: str, purpose: str) -> None:
    engine = create_engine(database_url)
    await engine.init(auto_create_tables=False)
    ctx = await OrgRepository(engine).authenticate(api_key)
    if ctx is None or not ctx.org_id:
        raise SystemExit("API key did not authenticate")
    owner = f"test-owner:{ctx.org_id}"
    expires = datetime.now(UTC) + timedelta(hours=1)
    root = build_root_authority_record(
        owner,
        RootType.HUMAN,
        "whitepact-test-suite",
        "explicit-test-fixture",
        organization_id=ctx.org_id,
        evidence_refs=("test-root-evidence",),
        expires_at=expires,
    )
    await RootAuthorityRepository(engine).create(root)
    consent = build_consent_proof(
        owner,
        root.root_id,
        ctx.key_id,
        "explicit test execution scope",
        purpose,
        ConsentMethod.EXPLICIT_UI_ACTION,
        allowed_action_types=(SYNTHETIC_COUNTER_TOOL,),
        allowed_targets=(SYNTHETIC_COUNTER_TOOL,),
        evidence_refs=("test-consent-evidence",),
        expires_at=expires,
    )
    await ConsentProofRepository(engine).create(consent, organization_id=ctx.org_id)
    await DelegationRepository(engine).grant(
        ctx.org_id,
        ctx.key_id,
        granted_action_types=frozenset({SYNTHETIC_COUNTER_TOOL}),
        constraints={"allowed_targets": [SYNTHETIC_COUNTER_TOOL]},
        purpose=purpose,
        granted_by=owner,
        expires_at=expires,
    )
    await PolicyRepository(engine).add_rule(
        ctx.org_id,
        PolicyRule(
            rule_id="require-test-counter",
            reason_code="TEST_COUNTER_REQUIRES_APPROVAL",
            effect=GovernanceDecision.REQUIRE_APPROVAL,
            action_types=frozenset({SYNTHETIC_COUNTER_TOOL}),
        ),
    )
    await engine.close()
    print(ctx.org_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--purpose", default="automated-test")
    args = parser.parse_args()
    asyncio.run(_seed(args.database_url, args.api_key, args.purpose))


if __name__ == "__main__":
    main()
