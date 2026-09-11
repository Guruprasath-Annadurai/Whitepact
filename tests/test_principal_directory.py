# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial tests for Principal Directory & Global Identifier Management."""

from __future__ import annotations

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.trust_fabric.directory import PrincipalDirectory, normalize_identifier
from responsibleai.trust_fabric.enums import (
    IdentifierType,
    IdentifierVerificationState,
    PrincipalState,
    PrincipalType,
)
from responsibleai.trust_fabric.errors import (
    CrossTenantAccessError,
    IdentifierCollisionError,
    PrincipalInactiveError,
)


@pytest.fixture
async def fabric_db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path}/test_tf.db"
    engine = create_engine(url)
    await engine.init()
    # Insert test organizations
    from responsibleai.db.engine import organizations
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert(),
            [
                {"id": "org_acme", "name": "Acme Corp", "slug": "acme", "created_at": "now"},
                {"id": "org_evil", "name": "Evil Corp", "slug": "evil", "created_at": "now"},
            ],
        )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.mark.asyncio
class TestPrincipalDirectory:
    async def test_identifier_normalization(self):
        # Email normalization: lowercase and IDN domain
        assert normalize_identifier(IdentifierType.EMAIL, "  Alice.Smith@Example.COM  ") == "alice.smith@example.com"
        with pytest.raises(ValueError):
            normalize_identifier(IdentifierType.EMAIL, "invalid-email")

        # Domain normalization: strip trailing dot, punycode
        assert normalize_identifier(IdentifierType.DOMAIN, "https://WWW.ACME.COM/path") == "www.acme.com"
        assert normalize_identifier(IdentifierType.DOMAIN, "münchen.de.") == "xn--mnchen-3ya.de"

        # Phone normalization: E.164
        assert normalize_identifier(IdentifierType.PHONE, "+1 (555) 019-2834") == "+15550192834"
        assert normalize_identifier(IdentifierType.PHONE, "15550192834") == "+15550192834"

        # Registration number: uppercase
        assert normalize_identifier(IdentifierType.REGISTRATION_NUMBER, "us_de:abc-1234") == "US_DE:ABC-1234"

    async def test_create_and_read_principal_tenant_isolation(self, fabric_db):
        dir_svc = PrincipalDirectory(fabric_db)

        # Create principal in Acme
        alice = await dir_svc.create_principal(
            org_id="org_acme",
            principal_type=PrincipalType.HUMAN,
            display_name="Alice Smith",
        )
        assert alice.id.startswith("wp_prin_")
        assert alice.org_id == "org_acme"

        # Read back in Acme: succeeds
        fetched = await dir_svc.get_principal(alice.id, org_id="org_acme")
        assert fetched.id == alice.id

        # Cross-tenant read from Evil Corp: BLOCKED
        with pytest.raises(CrossTenantAccessError):
            await dir_svc.get_principal(alice.id, org_id="org_evil")

    async def test_identifier_collision_prevented(self, fabric_db):
        dir_svc = PrincipalDirectory(fabric_db)

        p1 = await dir_svc.create_principal(
            org_id="org_acme", principal_type=PrincipalType.HUMAN, display_name="User 1"
        )
        p2 = await dir_svc.create_principal(
            org_id="org_acme", principal_type=PrincipalType.HUMAN, display_name="User 2"
        )

        # Attach email to p1
        await dir_svc.attach_identifier(
            principal_id=p1.id,
            org_id="org_acme",
            identifier_type=IdentifierType.EMAIL,
            value="support@acme.com",
            verification_state=IdentifierVerificationState.VERIFIED,
        )

        # Attempt to attach same email to p2 in same org: BLOCKED
        with pytest.raises(IdentifierCollisionError):
            await dir_svc.attach_identifier(
                principal_id=p2.id,
                org_id="org_acme",
                identifier_type=IdentifierType.EMAIL,
                value="SUPPORT@ACME.COM",  # Case variant
            )

        # Attaching same email in another org (org_evil) is allowed (tenant-scoped)
        p_evil = await dir_svc.create_principal(
            org_id="org_evil", principal_type=PrincipalType.HUMAN, display_name="Evil User"
        )
        ident_evil = await dir_svc.attach_identifier(
            principal_id=p_evil.id,
            org_id="org_evil",
            identifier_type=IdentifierType.EMAIL,
            value="support@acme.com",
        )
        assert ident_evil.org_id == "org_evil"

    async def test_principal_deletion_and_resurrection_prevention(self, fabric_db):
        dir_svc = PrincipalDirectory(fabric_db)

        # 1. Create employee Alice
        alice = await dir_svc.create_principal(
            org_id="org_acme", principal_type=PrincipalType.HUMAN, display_name="Alice Engineer"
        )
        await dir_svc.attach_identifier(
            principal_id=alice.id,
            org_id="org_acme",
            identifier_type=IdentifierType.EMAIL,
            value="dev@acme.com",
            verification_state=IdentifierVerificationState.VERIFIED,
        )

        # Resolve finds Alice
        resolved = await dir_svc.resolve_by_identifier(
            org_id="org_acme", identifier_type=IdentifierType.EMAIL, value="dev@acme.com"
        )
        assert resolved is not None
        assert resolved.id == alice.id

        # 2. Alice leaves company: delete principal
        await dir_svc.delete_principal(alice.id, org_id="org_acme")

        # Resolving now returns None (Alice is tombstoned)
        assert await dir_svc.resolve_by_identifier(
            org_id="org_acme", identifier_type=IdentifierType.EMAIL, value="dev@acme.com"
        ) is None

        # Cannot attach new identifiers to deleted principal
        with pytest.raises(PrincipalInactiveError):
            await dir_svc.attach_identifier(
                principal_id=alice.id,
                org_id="org_acme",
                identifier_type=IdentifierType.PHONE,
                value="+15551112222",
            )

        # 3. Months later, new employee Bob is hired and given the recycled email dev@acme.com
        bob = await dir_svc.create_principal(
            org_id="org_acme", principal_type=PrincipalType.HUMAN, display_name="Bob Engineer"
        )
        await dir_svc.attach_identifier(
            principal_id=bob.id,
            org_id="org_acme",
            identifier_type=IdentifierType.EMAIL,
            value="dev@acme.com",
            verification_state=IdentifierVerificationState.VERIFIED,
        )

        # Resurrection Defense: Bob has a completely NEW canonical principal_id
        assert bob.id != alice.id

        resolved_bob = await dir_svc.resolve_by_identifier(
            org_id="org_acme", identifier_type=IdentifierType.EMAIL, value="dev@acme.com"
        )
        assert resolved_bob is not None
        assert resolved_bob.id == bob.id

        # Historical Alice record is preserved as DELETED for audit, but separate from Bob
        alice_hist = await dir_svc.get_principal(alice.id, org_id="org_acme")
        assert alice_hist.lifecycle_state == PrincipalState.DELETED

    async def test_search_anti_enumeration(self, fabric_db):
        dir_svc = PrincipalDirectory(fabric_db)
        await dir_svc.create_principal(org_id="org_acme", principal_type=PrincipalType.HUMAN, display_name="Executive Acme")
        await dir_svc.create_principal(org_id="org_evil", principal_type=PrincipalType.HUMAN, display_name="Executive Evil")

        # Search in Acme only returns Acme principals
        results = await dir_svc.search_principals(org_id="org_acme", query="Executive")
        assert len(results) == 1
        assert results[0].org_id == "org_acme"
        assert results[0].display_name == "Executive Acme"
