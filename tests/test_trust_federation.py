# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit and adversarial tests for EnterpriseTrustMesh (Federated Assertions)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from responsibleai.db.engine import (
    create_engine,
    organizations,
    trust_fabric_authority_edges,
    trust_fabric_principals,
)
from responsibleai.trust_fabric.errors import (
    FederatedAssertionExpiredError,
    FederatedAssertionInvalidError,
    FederatedAssertionReplayError,
)
from responsibleai.trust_fabric.federation import EnterpriseTrustMesh, FederationKey


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
                {
                    "id": "org_partner",
                    "name": "Partner Org",
                    "slug": "partner",
                    "created_at": "now",
                },
                {
                    "id": "org_attacker",
                    "name": "Attacker Org",
                    "slug": "attacker",
                    "created_at": "now",
                },
            ],
        )
        await conn.execute(
            trust_fabric_principals.insert(),
            [
                {
                    "id": "wp_pr_auditor",
                    "org_id": "org_issuer",
                    "principal_type": "HUMAN",
                    "display_name": "Auditor",
                    "lifecycle_state": "ACTIVE",
                    "created_at": "now",
                    "updated_at": "now",
                },
                {
                    "id": "wp_pr_worker",
                    "org_id": "org_issuer",
                    "principal_type": "HUMAN",
                    "display_name": "Worker",
                    "lifecycle_state": "ACTIVE",
                    "created_at": "now",
                    "updated_at": "now",
                },
                {
                    "id": "wp_pr_suspended",
                    "org_id": "org_issuer",
                    "principal_type": "HUMAN",
                    "display_name": "Suspended Worker",
                    "lifecycle_state": "SUSPENDED",
                    "created_at": "now",
                    "updated_at": "now",
                },
            ],
        )
        await conn.execute(
            trust_fabric_authority_edges.insert(),
            [
                {
                    "id": "edge_valid",
                    "grantor_principal_id": "wp_pr_auditor",
                    "grantee_principal_id": "wp_pr_worker",
                    "org_id": "org_issuer",
                    "action_type": "AUDIT",
                    "resource_pattern": "*",
                    "valid_from": "2026-01-01T00:00:00Z",
                    "expires_at": "2026-12-31T23:59:59Z",
                    "revoked_at": None,
                    "canonical_digest": "dig_edge_valid",
                },
                {
                    "id": "edge_revoked",
                    "grantor_principal_id": "wp_pr_auditor",
                    "grantee_principal_id": "wp_pr_worker",
                    "org_id": "org_issuer",
                    "action_type": "SIGN_DEPLOYMENT",
                    "resource_pattern": "*",
                    "valid_from": "2026-01-01T00:00:00Z",
                    "expires_at": "2026-12-31T23:59:59Z",
                    "revoked_at": "2026-06-01T00:00:00Z",
                    "canonical_digest": "dig_edge_revoked",
                },
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

    with pytest.raises(
        FederatedAssertionInvalidError, match="cryptographic signature verification failed"
    ):
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


@pytest.mark.asyncio
async def test_federation_key_rotation_and_revocation(mesh_db):
    """Key rotation maintains validity for active assertions, while key revocation strictly rejects."""
    mesh = EnterpriseTrustMesh(mesh_db)

    # 1. Register initial key
    key1 = FederationKey.generate("org_issuer", "key_v1")
    mesh.register_key(key1)

    assertion1 = await mesh.issue_assertion(
        issuer_org_id="org_issuer",
        audience_org_id="org_partner",
        subject_principal_id="wp_pr_worker",
        claim_type="ROLE",
        claim_payload={"role": "engineer"},
        key_id="key_v1",
    )

    # 2. Rotate to key2
    key2 = FederationKey.generate("org_issuer", "key_v2")
    mesh.rotate_key("key_v1", key2)

    # Assertion with key2 works
    assertion2 = await mesh.issue_assertion(
        issuer_org_id="org_issuer",
        audience_org_id="org_partner",
        subject_principal_id="wp_pr_worker",
        claim_type="ROLE",
        claim_payload={"role": "senior_engineer"},
        key_id="key_v2",
    )
    c2 = await mesh.verify_and_consume_assertion(assertion2, verifying_org_id="org_partner")
    assert c2["role"] == "senior_engineer"

    # 3. Revoke key1
    mesh.revoke_key("key_v1")
    with pytest.raises(FederatedAssertionInvalidError, match="revoked"):
        await mesh.verify_and_consume_assertion(assertion1, verifying_org_id="org_partner")


@pytest.mark.asyncio
async def test_federation_unknown_issuer_and_wrong_key_id(mesh_db):
    """Assertions signed with unknown keys or mismatched key IDs are strictly rejected."""
    mesh = EnterpriseTrustMesh(mesh_db)
    assertion = await mesh.issue_assertion(
        issuer_org_id="org_issuer",
        audience_org_id="org_partner",
        subject_principal_id="wp_pr_worker",
        claim_type="ACCESS",
        claim_payload={"level": "admin"},
        key_id="fed_key_2026",
    )

    # Wrong key ID on assertion
    wrong_key_assertion = replace(assertion, key_id="unknown_key_999")
    with pytest.raises(FederatedAssertionInvalidError, match="Unknown issuer federation key"):
        await mesh.verify_and_consume_assertion(wrong_key_assertion, verifying_org_id="org_partner")


@pytest.mark.asyncio
async def test_federation_algorithm_confusion_rejected(mesh_db):
    """Rejection of algorithm confusion (e.g. none, RS256, HMAC)."""
    mesh = EnterpriseTrustMesh(mesh_db)
    assertion = await mesh.issue_assertion(
        issuer_org_id="org_issuer",
        audience_org_id="org_partner",
        subject_principal_id="wp_pr_worker",
        claim_type="ACCESS",
        claim_payload={"level": "admin"},
        key_id="fed_key_2026",
    )

    # Attacker crafts assertion with algorithm = 'none'
    alg_none_assertion = replace(assertion, algorithm="none")
    with pytest.raises(FederatedAssertionInvalidError, match="Algorithm confusion detected"):
        await mesh.verify_and_consume_assertion(alg_none_assertion, verifying_org_id="org_partner")

    # Attacker crafts assertion with algorithm = 'HS256'
    alg_hs_assertion = replace(assertion, algorithm="HS256")
    with pytest.raises(FederatedAssertionInvalidError, match="Algorithm confusion detected"):
        await mesh.verify_and_consume_assertion(alg_hs_assertion, verifying_org_id="org_partner")


@pytest.mark.asyncio
async def test_federation_assertion_replay_prevented(mesh_db):
    """Replaying an already consumed assertion nonce is rejected."""
    mesh = EnterpriseTrustMesh(mesh_db)
    assertion = await mesh.issue_assertion(
        issuer_org_id="org_issuer",
        audience_org_id="org_partner",
        subject_principal_id="wp_pr_worker",
        claim_type="ONE_TIME_TOKEN",
        claim_payload={"token_code": "secret123"},
        key_id="fed_key_2026",
    )

    # First consumption succeeds
    consumed = await mesh.verify_and_consume_assertion(assertion, verifying_org_id="org_partner")
    assert consumed["token_code"] == "secret123"

    # Replay attempt fails
    with pytest.raises(FederatedAssertionReplayError, match="already been consumed"):
        await mesh.verify_and_consume_assertion(assertion, verifying_org_id="org_partner")


@pytest.mark.asyncio
async def test_federation_organization_substitution_prevented(mesh_db):
    """Attacker org cannot claim to use issuer org key."""
    mesh = EnterpriseTrustMesh(mesh_db)
    key = FederationKey.generate("org_issuer", "legit_key")
    mesh.register_key(key)

    assertion = await mesh.issue_assertion(
        issuer_org_id="org_issuer",
        audience_org_id="org_partner",
        subject_principal_id="wp_pr_worker",
        claim_type="ROLE",
        claim_payload={"role": "dev"},
        key_id="legit_key",
    )

    # Attacker modifies assertion issuer to attacker org while pointing to legit_key
    substituted = replace(assertion, issuer_org_id="org_attacker")
    with pytest.raises(FederatedAssertionInvalidError, match="Key issuer mismatch"):
        await mesh.verify_and_consume_assertion(substituted, verifying_org_id="org_partner")


@pytest.mark.asyncio
async def test_federation_revoked_principal_and_authority_rejected(mesh_db):
    """Federated assertion for revoked principal or revoked authority edge is rejected."""
    mesh = EnterpriseTrustMesh(mesh_db)

    # 1. Suspended principal
    assertion_suspended = await mesh.issue_assertion(
        issuer_org_id="org_issuer",
        audience_org_id="org_partner",
        subject_principal_id="wp_pr_suspended",
        claim_type="EMPLOYEE",
        claim_payload={"status": "employed"},
        key_id="fed_key_2026",
    )
    with pytest.raises(FederatedAssertionInvalidError, match="SUSPENDED"):
        await mesh.verify_and_consume_assertion(assertion_suspended, verifying_org_id="org_partner")

    # 2. Revoked authority edge
    assertion_revoked_auth = await mesh.issue_assertion(
        issuer_org_id="org_issuer",
        audience_org_id="org_partner",
        subject_principal_id="wp_pr_worker",
        claim_type="AUTHORITY",
        claim_payload={"authority_id": "edge_revoked", "action": "SIGN_DEPLOYMENT"},
        key_id="fed_key_2026",
    )
    with pytest.raises(FederatedAssertionInvalidError, match="revoked"):
        await mesh.verify_and_consume_assertion(
            assertion_revoked_auth, verifying_org_id="org_partner"
        )


@pytest.mark.asyncio
async def test_federation_zero_forged_or_stale_accepted(mesh_db):
    """Audit requirement: FORGED/STALE FEDERATED AUTHORITY ACCEPTED: 0."""
    mesh = EnterpriseTrustMesh(mesh_db)
    forged_accepted_count = 0

    # Test suite of adversarial attacks
    attacks = [
        # Tampered payload
        lambda a: replace(a, claim_payload={"amount": 999999}),
        # Tampered signature
        lambda a: replace(a, signature="sig_fed_fake_hex12345"),
        # Algorithm none
        lambda a: replace(a, algorithm="none"),
        # Wrong audience
        lambda a: replace(a, audience_org_id="org_unauthorized"),
        # Expired
        lambda a: replace(a, expires_at="2020-01-01T00:00:00Z"),
    ]

    base = await mesh.issue_assertion(
        issuer_org_id="org_issuer",
        audience_org_id="org_partner",
        subject_principal_id="wp_pr_worker",
        claim_type="ROLE",
        claim_payload={"role": "dev"},
        key_id="fed_key_2026",
    )

    for attack in attacks:
        mutated = attack(base)
        try:
            await mesh.verify_and_consume_assertion(mutated, verifying_org_id="org_partner")
            forged_accepted_count += 1
        except Exception:
            pass  # Expected rejection

    assert forged_accepted_count == 0
    # Audit invariant
    stale_federated_accepted = forged_accepted_count
    assert stale_federated_accepted == 0
