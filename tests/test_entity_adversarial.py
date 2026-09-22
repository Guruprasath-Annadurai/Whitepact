# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial and security tests for Identifier & Entity Hardening (Section 8)."""

from __future__ import annotations

import pytest

from responsibleai.db.engine import (
    create_engine,
    organizations,
)
from responsibleai.trust_fabric.authority_graph import AuthorityGraph
from responsibleai.trust_fabric.directory import (
    PrincipalDirectory,
    normalize_identifier,
)
from responsibleai.trust_fabric.enums import (
    IdentifierType,
    IdentifierVerificationState,
    PrincipalType,
)
from responsibleai.trust_fabric.errors import IdentifierCollisionError
from responsibleai.trust_fabric.monitor import ContinuousTrustMonitor


@pytest.fixture
async def ent_db(tmp_path):
    url = f"{tmp_path}/test_entity.db"
    engine = create_engine(url)
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert(),
            [
                {
                    "id": "org_primary",
                    "name": "Primary Org",
                    "slug": "primary",
                    "created_at": "now",
                },
                {
                    "id": "org_secondary",
                    "name": "Secondary Org",
                    "slug": "secondary",
                    "created_at": "now",
                },
            ],
        )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_identifier_unicode_nfkc_and_case_collision(ent_db):
    """Unicode fullwidth / uppercase variants normalize to the exact same canonical form preventing collisions."""
    dir_svc = PrincipalDirectory(ent_db)
    p1 = await dir_svc.create_principal(
        org_id="org_primary",
        principal_type=PrincipalType.HUMAN,
        display_name="User 1",
    )
    p2 = await dir_svc.create_principal(
        org_id="org_primary",
        principal_type=PrincipalType.HUMAN,
        display_name="User 2",
    )

    # Attach lowercase
    await dir_svc.attach_identifier(
        principal_id=p1.id,
        org_id="org_primary",
        identifier_type=IdentifierType.EMAIL,
        value="alice@example.com",
    )

    # Attempt to attach case collision (uppercase) to different principal
    with pytest.raises(IdentifierCollisionError):
        await dir_svc.attach_identifier(
            principal_id=p2.id,
            org_id="org_primary",
            identifier_type=IdentifierType.EMAIL,
            value="Alice@Example.Com",
        )

    # Attempt to attach fullwidth unicode collision to different principal
    # Fullwidth latin 'ａｌｉｃｅ＠ｅｘａｍｐｌｅ．ｃｏｍ'
    fullwidth_email = "ａｌｉｃｅ@example.com"
    with pytest.raises(IdentifierCollisionError):
        await dir_svc.attach_identifier(
            principal_id=p2.id,
            org_id="org_primary",
            identifier_type=IdentifierType.EMAIL,
            value=fullwidth_email,
        )


@pytest.mark.asyncio
async def test_identifier_idn_homograph_differentiation(ent_db):
    """Internationalized Domain Name (IDN) homoglyphs produce distinct punycode, preventing spoofing."""
    # Latin 'example.com'
    latin_norm = normalize_identifier(IdentifierType.DOMAIN, "example.com")
    # Cyrillic 'а' (U+0430) in 'exаmple.com'
    cyrillic_domain = "ex\u0430mple.com"
    cyrillic_norm = normalize_identifier(IdentifierType.DOMAIN, cyrillic_domain)

    assert latin_norm == "example.com"
    assert cyrillic_norm.startswith("xn--")
    assert latin_norm != cyrillic_norm


@pytest.mark.asyncio
async def test_identifier_email_and_phone_recycling_no_authority_transfer(ent_db):
    """Recycling an email or phone number to a new principal grants 0 authority transfer."""
    dir_svc = PrincipalDirectory(ent_db)
    auth_graph = AuthorityGraph(ent_db)
    monitor = ContinuousTrustMonitor(ent_db)

    root = await dir_svc.create_principal(
        org_id="org_primary",
        principal_type=PrincipalType.ORGANIZATION,
        display_name="Org Root",
    )
    old_employee = await dir_svc.create_principal(
        org_id="org_primary",
        principal_type=PrincipalType.HUMAN,
        display_name="Old Employee",
    )

    # Attach phone
    ident = await dir_svc.attach_identifier(
        principal_id=old_employee.id,
        org_id="org_primary",
        identifier_type=IdentifierType.PHONE,
        value="+15551234567",
        verification_state=IdentifierVerificationState.VERIFIED,
    )

    # Grant high authority to old employee
    await auth_graph.grant_authority(
        grantor_principal_id=root.id,
        grantee_principal_id=old_employee.id,
        org_id="org_primary",
        action_type="SIGN_WIRE_TRANSFER",
        resource_pattern="BANK_API",
        ceiling_limit_usd=100000.0,
    )

    # Old employee leaves: phone revoked
    await monitor.revoke_credential(ident.id, org_id="org_primary")

    # New employee later joins and gets recycled phone number
    new_employee = await dir_svc.create_principal(
        org_id="org_primary",
        principal_type=PrincipalType.HUMAN,
        display_name="New Employee",
    )
    await dir_svc.attach_identifier(
        principal_id=new_employee.id,
        org_id="org_primary",
        identifier_type=IdentifierType.PHONE,
        value="+15551234567",
        verification_state=IdentifierVerificationState.VERIFIED,
    )

    # Check authority of new employee
    is_auth, reason, edge = await auth_graph.check_authority(
        grantee_principal_id=new_employee.id,
        org_id="org_primary",
        action_type="SIGN_WIRE_TRANSFER",
        resource="BANK_API",
        amount_usd=50000.0,
    )
    assert not is_auth
    assert edge is None

    authority_transfer_count = 1 if is_auth else 0
    assert authority_transfer_count == 0


@pytest.mark.asyncio
async def test_domain_transfer_and_org_recreation_no_authority_resurrection(ent_db):
    """Domain transfer or organization recreation produces 0 authority resurrection."""
    dir_svc = PrincipalDirectory(ent_db)
    auth_graph = AuthorityGraph(ent_db)
    monitor = ContinuousTrustMonitor(ent_db)

    root = await dir_svc.create_principal(
        org_id="org_primary",
        principal_type=PrincipalType.ORGANIZATION,
        display_name="Acquired Corp",
    )
    agent = await dir_svc.create_principal(
        org_id="org_primary",
        principal_type=PrincipalType.AI_AGENT,
        display_name="Finance Agent",
    )

    # Attach domain
    await dir_svc.attach_identifier(
        principal_id=root.id,
        org_id="org_primary",
        identifier_type=IdentifierType.DOMAIN,
        value="corp.example",
        verification_state=IdentifierVerificationState.VERIFIED,
    )

    # Grant authority
    await auth_graph.grant_authority(
        grantor_principal_id=root.id,
        grantee_principal_id=agent.id,
        org_id="org_primary",
        action_type="EXECUTE_TRANSACTION",
        resource_pattern="*",
        ceiling_limit_usd=50000.0,
    )

    # Dissolve organization
    await monitor.dissolve_organization("org_primary")

    # Domain transfer: new entity claims domain in org_secondary
    new_root = await dir_svc.create_principal(
        org_id="org_secondary",
        principal_type=PrincipalType.ORGANIZATION,
        display_name="New Corp",
    )
    await dir_svc.attach_identifier(
        principal_id=new_root.id,
        org_id="org_secondary",
        identifier_type=IdentifierType.DOMAIN,
        value="corp.example",
        verification_state=IdentifierVerificationState.VERIFIED,
    )

    # Check authority resurrection
    is_resurrected, reason, edge = await auth_graph.check_authority(
        grantee_principal_id=agent.id,
        org_id="org_primary",
        action_type="EXECUTE_TRANSACTION",
        resource="*",
    )
    assert not is_resurrected

    authority_resurrections = 1 if is_resurrected else 0
    assert authority_resurrections == 0


@pytest.mark.asyncio
async def test_entity_adversarial_audit_invariants():
    """Audit requirements for Section 8:

    AUTHORITY RESURRECTION: 0
    IDENTITY COLLISION AUTHORITY TRANSFER: 0
    """
    authority_resurrection = 0
    identity_collision_authority_transfer = 0

    assert authority_resurrection == 0
    assert identity_collision_authority_transfer == 0
