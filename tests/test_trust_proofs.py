# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial tests for Trust Proofs Engine."""

from __future__ import annotations

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.trust_fabric.authority_graph import AuthorityGraph
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import (
    IdentifierVerificationState,
    PrincipalType,
    ProofStatus,
    RelationshipType,
    SourceTier,
)
from responsibleai.trust_fabric.proofs import TrustProofEngine
from responsibleai.trust_fabric.provenance import TrustProvenanceEngine


@pytest.fixture
async def proof_db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path}/test_proof.db"
    engine = create_engine(url)
    await engine.init()
    from responsibleai.db.engine import organizations

    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert(),
            [{"id": "org_corp", "name": "Global Corp", "slug": "gcorp", "created_at": "now"}],
        )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.mark.asyncio
class TestTrustProofs:
    async def test_employment_proof(self, proof_db):
        dir_svc = PrincipalDirectory(proof_db)
        auth_svc = AuthorityGraph(proof_db)
        proof_svc = TrustProofEngine(proof_db)
        prov_svc = TrustProvenanceEngine(proof_db)

        src = await prov_svc.register_source(
            name="HR Source", source_tier=SourceTier.TIER_C, provider_type="IDP", org_id="org_corp"
        )
        alice = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Alice"
        )
        company = await dir_svc.create_principal(
            org_id="org_corp",
            principal_type=PrincipalType.ORGANIZATION,
            display_name="Global Corp Org",
        )

        # Before relationship: NOT_PROVEN
        status = await proof_svc.prove_employment(principal_id=alice.id, org_id="org_corp")
        assert status == ProofStatus.NOT_PROVEN

        # Establish employment relationship
        rel = await auth_svc.create_relationship(
            subject_principal_id=alice.id,
            target_principal_id=company.id,
            org_id="org_corp",
            relationship_type=RelationshipType.EMPLOYED_BY,
            source_id=src.id,
            role_title="Software Architect",
            verification_state=IdentifierVerificationState.VERIFIED,
        )

        # Now: PROVEN
        status2 = await proof_svc.prove_employment(principal_id=alice.id, org_id="org_corp")
        assert status2 == ProofStatus.PROVEN

        # Revoke relationship: REVOKED
        await auth_svc.revoke_relationship(rel.id, org_id="org_corp")
        status3 = await proof_svc.prove_employment(principal_id=alice.id, org_id="org_corp")
        assert status3 == ProofStatus.REVOKED

    async def test_signing_authority_proof_and_ceiling(self, proof_db):
        dir_svc = PrincipalDirectory(proof_db)
        auth_svc = AuthorityGraph(proof_db)
        proof_svc = TrustProofEngine(proof_db)

        grantor = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="CEO Grantor"
        )
        grantee = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Purchasing Agent"
        )

        # Grant $500,000 signing authority
        await auth_svc.grant_authority(
            grantor_principal_id=grantor.id,
            grantee_principal_id=grantee.id,
            org_id="org_corp",
            action_type="contract.sign",
            resource_pattern="contract:supplier:*",
            ceiling_limit_usd=500_000.0,
        )

        # Within ceiling ($250,000) -> PROVEN
        res_ok = await proof_svc.prove_signing_authority(
            principal_id=grantee.id, org_id="org_corp", amount_usd=250_000.0
        )
        assert res_ok == ProofStatus.PROVEN

        # Exceeding ceiling ($750,000) -> NOT_PROVEN
        res_exceeded = await proof_svc.prove_signing_authority(
            principal_id=grantee.id, org_id="org_corp", amount_usd=750_000.0
        )
        assert res_exceeded == ProofStatus.NOT_PROVEN

    async def test_agent_ownership_proof(self, proof_db):
        dir_svc = PrincipalDirectory(proof_db)
        proof_svc = TrustProofEngine(proof_db)

        agent = await dir_svc.create_principal(
            org_id="org_corp",
            principal_type=PrincipalType.AI_AGENT,
            display_name="Accounting Bot 1",
        )
        # Directly in org_corp and active
        res = await proof_svc.prove_agent_ownership(agent_principal_id=agent.id, org_id="org_corp")
        assert res == ProofStatus.PROVEN

        # Non-existent agent -> UNKNOWN
        res_unk = await proof_svc.prove_agent_ownership(
            agent_principal_id="wp_prin_nonexistent", org_id="org_corp"
        )
        assert res_unk == ProofStatus.UNKNOWN
