# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit and adversarial tests for TrustConflictEngine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from responsibleai.db.engine import (
    create_engine,
    organizations,
    trust_fabric_assertions,
)
from responsibleai.trust_fabric.conflict import TrustConflictEngine
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import (
    AssuranceLevel,
    ConflictStatus,
    ConflictType,
    DisclosureClass,
    PrincipalType,
    SourceTier,
)
from responsibleai.trust_fabric.errors import CrossTenantAccessError
from responsibleai.trust_fabric.provenance import TrustProvenanceEngine


@pytest.fixture
async def sqlite_engine(tmp_path):
    url = f"{tmp_path}/test_conflict.db"
    engine = create_engine(url)
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert(),
            [
                {"id": "org_acme_corp", "name": "Acme Corp", "slug": "acme", "created_at": "now"},
                {"id": "org_fresh_test", "name": "Fresh Org", "slug": "fresh", "created_at": "now"},
                {"id": "org_equal_test", "name": "Equal Org", "slug": "equal", "created_at": "now"},
                {"id": "org_alpha", "name": "Org Alpha", "slug": "alpha", "created_at": "now"},
                {"id": "org_beta", "name": "Org Beta", "slug": "beta", "created_at": "now"},
            ],
        )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_conflict_higher_tier_supersedes_lower(sqlite_engine):
    """Tier B authoritative registry assertion supersedes Tier F self-attestation."""
    org_id = "org_acme_corp"
    dir_svc = PrincipalDirectory(sqlite_engine)
    prov = TrustProvenanceEngine(sqlite_engine)
    conflict_engine = TrustConflictEngine(sqlite_engine)

    principal = await dir_svc.create_principal(
        org_id=org_id,
        principal_type=PrincipalType.ORGANIZATION,
        display_name="Acme Corp GmbH",
    )

    src_b = await prov.register_source(
        name="DE_Commercial_Register",
        source_tier=SourceTier.TIER_B,
        provider_type="REGISTRY_API",
        org_id=org_id,
    )
    src_f = await prov.register_source(
        name="Self_Reported_Profile",
        source_tier=SourceTier.TIER_F,
        provider_type="USER_FORM",
        org_id=org_id,
    )

    asst_b = await prov.record_assertion(
        principal_id=principal.id,
        org_id=org_id,
        field_name="legal_name",
        field_value="Acme Corp GmbH",
        source_id=src_b.id,
        verification_method="REGISTRY_API",
        assurance_level=AssuranceLevel.HIGH,
        disclosure_class=DisclosureClass.BUSINESS_PUBLIC,
    )
    asst_f = await prov.record_assertion(
        principal_id=principal.id,
        org_id=org_id,
        field_name="legal_name",
        field_value="Acme Global International",
        source_id=src_f.id,
        verification_method="USER_FORM",
        assurance_level=AssuranceLevel.LOW,
        disclosure_class=DisclosureClass.BUSINESS_PUBLIC,
    )

    conflict = await conflict_engine.record_conflict(
        principal_id=principal.id,
        org_id=org_id,
        field_or_claim="legal_name",
        assertion_id_a=asst_b.id,
        assertion_id_b=asst_f.id,
        conflict_type=ConflictType.VALUE_CONTRADICTION,
    )
    assert conflict.status == ConflictStatus.UNRESOLVED

    status, reason = await conflict_engine.evaluate_and_resolve(conflict.id, org_id=org_id)
    assert status == ConflictStatus.RESOLVED_SUPERSEDED
    assert "TIER_B" in reason and "supersedes" in reason


@pytest.mark.asyncio
async def test_conflict_fresh_supersedes_stale(sqlite_engine):
    """Equal tier: fresh authoritative assertion supersedes stale (>30d)."""
    org_id = "org_fresh_test"
    dir_svc = PrincipalDirectory(sqlite_engine)
    prov = TrustProvenanceEngine(sqlite_engine)
    conflict_engine = TrustConflictEngine(sqlite_engine)

    principal = await dir_svc.create_principal(
        org_id=org_id,
        principal_type=PrincipalType.SERVICE,
        display_name="Fresh Service",
    )
    src = await prov.register_source(
        name="Okta_IdP",
        source_tier=SourceTier.TIER_C,
        provider_type="SAML_SCIM",
        org_id=org_id,
    )

    asst_stale = await prov.record_assertion(
        principal_id=principal.id,
        org_id=org_id,
        field_name="ip_allowlist",
        field_value="10.0.0.1",
        source_id=src.id,
        verification_method="SAML_SCIM",
        assurance_level=AssuranceLevel.MEDIUM,
        disclosure_class=DisclosureClass.TENANT_INTERNAL,
    )
    asst_fresh = await prov.record_assertion(
        principal_id=principal.id,
        org_id=org_id,
        field_name="ip_allowlist",
        field_value="10.0.0.2",
        source_id=src.id,
        verification_method="SAML_SCIM",
        assurance_level=AssuranceLevel.MEDIUM,
        disclosure_class=DisclosureClass.TENANT_INTERNAL,
    )

    # Backdate asst_stale by 60 days
    old_time = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            update(trust_fabric_assertions)
            .where(trust_fabric_assertions.c.id == asst_stale.id)
            .values(verified_at=old_time)
        )

    conflict = await conflict_engine.record_conflict(
        principal_id=principal.id,
        org_id=org_id,
        field_or_claim="ip_allowlist",
        assertion_id_a=asst_stale.id,
        assertion_id_b=asst_fresh.id,
    )

    status, reason = await conflict_engine.evaluate_and_resolve(conflict.id, org_id=org_id)
    assert status == ConflictStatus.RESOLVED_SUPERSEDED
    assert "freshness" in reason.lower()


@pytest.mark.asyncio
async def test_conflict_equal_tier_concurrent_requires_review(sqlite_engine):
    """Equal tier with contemporary timestamps cannot be auto-resolved."""
    org_id = "org_equal_test"
    dir_svc = PrincipalDirectory(sqlite_engine)
    prov = TrustProvenanceEngine(sqlite_engine)
    conflict_engine = TrustConflictEngine(sqlite_engine)

    principal = await dir_svc.create_principal(
        org_id=org_id,
        principal_type=PrincipalType.HUMAN,
        display_name="Equal Human",
    )
    src_1 = await prov.register_source(
        name="Hardware_Yubikey_1",
        source_tier=SourceTier.TIER_A,
        provider_type="WEBAUTHN",
        org_id=org_id,
    )
    src_2 = await prov.register_source(
        name="Hardware_Yubikey_2",
        source_tier=SourceTier.TIER_A,
        provider_type="WEBAUTHN",
        org_id=org_id,
    )

    asst_1 = await prov.record_assertion(
        principal_id=principal.id,
        org_id=org_id,
        field_name="signing_key_fp",
        field_value="fp_aaaa_1111",
        source_id=src_1.id,
        verification_method="WEBAUTHN",
        assurance_level=AssuranceLevel.CRYPTOGRAPHIC,
        disclosure_class=DisclosureClass.PUBLIC,
    )
    asst_2 = await prov.record_assertion(
        principal_id=principal.id,
        org_id=org_id,
        field_name="signing_key_fp",
        field_value="fp_bbbb_2222",
        source_id=src_2.id,
        verification_method="WEBAUTHN",
        assurance_level=AssuranceLevel.CRYPTOGRAPHIC,
        disclosure_class=DisclosureClass.PUBLIC,
    )

    # Backdate asst_1 by only 1 day (so delta < 30 days)
    yesterday = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            update(trust_fabric_assertions)
            .where(trust_fabric_assertions.c.id == asst_1.id)
            .values(verified_at=yesterday)
        )

    conflict = await conflict_engine.record_conflict(
        principal_id=principal.id,
        org_id=org_id,
        field_or_claim="signing_key_fp",
        assertion_id_a=asst_1.id,
        assertion_id_b=asst_2.id,
    )

    status, reason = await conflict_engine.evaluate_and_resolve(conflict.id, org_id=org_id)
    assert status == ConflictStatus.UNRESOLVED
    assert "requires human review" in reason


@pytest.mark.asyncio
async def test_conflict_cross_tenant_isolation(sqlite_engine):
    """Tenant A cannot resolve or inspect Tenant B's conflict record."""
    org_a = "org_alpha"
    org_b = "org_beta"
    dir_svc = PrincipalDirectory(sqlite_engine)
    conflict_engine = TrustConflictEngine(sqlite_engine)

    principal = await dir_svc.create_principal(
        org_id=org_a,
        principal_type=PrincipalType.ORGANIZATION,
        display_name="Iso Conflict Org",
    )

    conflict = await conflict_engine.record_conflict(
        principal_id=principal.id,
        org_id=org_a,
        field_or_claim="root_jurisdiction",
        assertion_id_a="asst_1",
        assertion_id_b="asst_2",
    )

    with pytest.raises(CrossTenantAccessError):
        await conflict_engine.evaluate_and_resolve(conflict.id, org_id=org_b)
