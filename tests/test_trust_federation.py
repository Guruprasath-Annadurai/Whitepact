# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit and adversarial tests for EnterpriseTrustMesh (Federated Assertions)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from responsibleai.db.engine import (
    create_engine,
    organizations,
)
from responsibleai.trust_fabric.errors import (
    FederatedAssertionExpiredError,
    FederatedAssertionInvalidError,
)
from responsibleai.trust_fabric.federation import EnterpriseTrustMesh


@pytest.fixture
async def mesh_db(tmp_path):
    url = f"{tmp_path}/test_mesh.db"
    engine = create_engine(url)
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert(),
            [
                {"id": "org_issuer", "name": "Issuer Org", "slug": "issuer", "created_at": "now"},
                {"id": "org_partner", "name": "Partner Org", "slug": "partner", "created_at": "now"},
                {"id": "org_attacker", "name": "Attacker Org", "slug": "attacker", "created_at": "now"},
            ],
        )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_federation_legitimate_cross_org_assertion(mesh_db):
    """Legitimate cross-org assertion issued and verified cleanly."""
    mesh = EnterpriseTrustMesh(mesh_db)
    assertion = await mesh.issue_assertion(
        issuer_org_id="org_issuer",
        audience_org_id="org_partner",
        subject_principal_id="wp_pr_auditor",
        claim_type="SECURITY_CLEARANCE",
        claim_payload={"clearance_level": "TOP_SECRET", "audited": True},
        key_id="fed_key_2026",
        ttl_minutes=30,
    )
    assert assertion.id.startswith("wp_fed_")
    assert assertion.signature.startswith("sig_fed_")

    claims = await mesh.verify_and_consume_assertion(
        assertion,
        verifying_org_id="org_partner",
        expected_subject_id="wp_pr_auditor",
        expected_issuer_id="org_issuer",
    )
    assert claims["clearance_level"] == "TOP_SECRET"
    assert claims["audited"] is True


@pytest.mark.asyncio
async def test_federation_audience_confusion_prevented(mesh_db):
    """Assertion issued for Partner Org cannot be replayed or submitted to Attacker Org."""
    mesh = EnterpriseTrustMesh(mesh_db)
    assertion = await mesh.issue_assertion(
        issuer_org_id="org_issuer",
        audience_org_id="org_partner",
        subject_principal_id="wp_pr_worker",
        claim_type="EMPLOYEE_VERIFIED",
        claim_payload={"status": "active"},
        key_id="fed_key_2026",
    )

    # Submitted to org_attacker
    with pytest.raises(FederatedAssertionInvalidError, match="Audience confusion detected"):
        await mesh.verify_and_consume_assertion(
            assertion,
            verifying_org_id="org_attacker",
        )


@pytest.mark.asyncio
async def test_federation_issuer_and_subject_substitution_prevented(mesh_db):
    """Assertion issuer or subject cannot be substituted."""
    mesh = EnterpriseTrustMesh(mesh_db)
    assertion = await mesh.issue_assertion(
        issuer_org_id="org_issuer",
        audience_org_id="org_partner",
        subject_principal_id="wp_pr_worker",
        claim_type="EMPLOYEE_VERIFIED",
        claim_payload={"status": "active"},
        key_id="fed_key_2026",
    )

    # Issuer substitution
    with pytest.raises(FederatedAssertionInvalidError, match="Issuer substitution detected"):
        await mesh.verify_and_consume_assertion(
            assertion,
            verifying_org_id="org_partner",
            expected_issuer_id="org_attacker",
        )

    # Subject substitution
    with pytest.raises(FederatedAssertionInvalidError, match="Subject substitution detected"):
        await mesh.verify_and_consume_assertion(
            assertion,
            verifying_org_id="org_partner",
            expected_subject_id="wp_pr_different_person",
        )


@pytest.mark.asyncio
async def test_federation_tampering_prevented(mesh_db):
    """Modifying claim payload breaks cryptographic signature verification."""
    mesh = EnterpriseTrustMesh(mesh_db)
    assertion = await mesh.issue_assertion(
        issuer_org_id="org_issuer",
        audience_org_id="org_partner",
        subject_principal_id="wp_pr_worker",
        claim_type="PAYMENT_AUTHORIZATION",
        claim_payload={"amount_limit": 500},
        key_id="fed_key_2026",
    )

    # Tamper with payload (escalate amount to 500000)
    tampered_assertion = replace(assertion, claim_payload={"amount_limit": 500000})

    with pytest.raises(FederatedAssertionInvalidError, match="cryptographic signature verification failed"):
        await mesh.verify_and_consume_assertion(
            tampered_assertion,
            verifying_org_id="org_partner",
        )


@pytest.mark.asyncio
async def test_federation_expired_assertion_rejected(mesh_db):
    """Expired assertions are strictly rejected."""
    mesh = EnterpriseTrustMesh(mesh_db)
    assertion = await mesh.issue_assertion(
        issuer_org_id="org_issuer",
        audience_org_id="org_partner",
        subject_principal_id="wp_pr_worker",
        claim_type="TEMPORARY_PASS",
        claim_payload={"role": "guest"},
        key_id="fed_key_2026",
        ttl_minutes=-10,  # Expired in past
    )

    with pytest.raises(FederatedAssertionExpiredError, match="expired"):
        await mesh.verify_and_consume_assertion(
            assertion,
            verifying_org_id="org_partner",
        )
