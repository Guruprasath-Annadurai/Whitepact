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


@pytest.mark.asyncio
async def test_old_registry_cannot_override_fresh_employment_termination(sqlite_engine):
    """Old statutory registry (Tier B) cannot override fresh enterprise HRIS termination (Tier C)."""
    org_id = "org_acme_corp"
    dir_svc = PrincipalDirectory(sqlite_engine)
    prov = TrustProvenanceEngine(sqlite_engine)
    conflict_engine = TrustConflictEngine(sqlite_engine)

    employee = await dir_svc.create_principal(
        org_id=org_id, principal_type=PrincipalType.HUMAN, display_name="Former Employee"
    )

    src_reg = await prov.register_source(
        name="State_Corporate_Filing_2yr_Old",
        source_tier=SourceTier.TIER_B,
        provider_type="STATUTORY_REGISTRY",
        org_id=org_id,
    )
    src_hr = await prov.register_source(
        name="Workday_HRIS_Live",
        source_tier=SourceTier.TIER_C,
        provider_type="ENTERPRISE_HRIS",
        org_id=org_id,
    )

    asst_old_reg = await prov.record_assertion(
        principal_id=employee.id,
        org_id=org_id,
        field_name="CURRENT_EMPLOYMENT",
        field_value="EMPLOYED",
        source_id=src_reg.id,
        verification_method="ANNUAL_FILING",
        assurance_level=AssuranceLevel.HIGH,
        disclosure_class=DisclosureClass.BUSINESS_PUBLIC,
    )
    asst_fresh_hr = await prov.record_assertion(
        principal_id=employee.id,
        org_id=org_id,
        field_name="CURRENT_EMPLOYMENT",
        field_value="TERMINATED",
        source_id=src_hr.id,
        verification_method="HR_SCIM_EVENT",
        assurance_level=AssuranceLevel.HIGH,
        disclosure_class=DisclosureClass.TENANT_INTERNAL,
    )

    conflict = await conflict_engine.record_conflict(
        principal_id=employee.id,
        org_id=org_id,
        field_or_claim="CURRENT_EMPLOYMENT",
        assertion_id_a=asst_old_reg.id,
        assertion_id_b=asst_fresh_hr.id,
    )

    status, reason = await conflict_engine.evaluate_and_resolve(conflict.id, org_id=org_id)
    assert status == ConflictStatus.RESOLVED_SUPERSEDED
    # Assertion B (Workday HRIS Tier C) strictly supersedes Assertion A (Statutory Filing Tier B) for employment
    assert "Assertion B (TIER_C) is authoritative for CURRENT_EMPLOYMENT" in reason


@pytest.mark.asyncio
async def test_old_public_role_cannot_override_fresh_enterprise_role_removal(sqlite_engine):
    """Old public directory role assertion cannot override fresh enterprise directory removal."""
    org_id = "org_acme_corp"
    dir_svc = PrincipalDirectory(sqlite_engine)
    prov = TrustProvenanceEngine(sqlite_engine)
    conflict_engine = TrustConflictEngine(sqlite_engine)

    principal = await dir_svc.create_principal(
        org_id=org_id, principal_type=PrincipalType.HUMAN, display_name="Demoted Executive"
    )

    src_pub = await prov.register_source(
        name="Public_Business_Registry",
        source_tier=SourceTier.TIER_E,
        provider_type="PUBLIC_DIRECTORY",
        org_id=org_id,
    )
    src_idp = await prov.register_source(
        name="Okta_Directory_Live",
        source_tier=SourceTier.TIER_C,
        provider_type="ENTERPRISE_IDP",
        org_id=org_id,
    )

    asst_old_pub = await prov.record_assertion(
        principal_id=principal.id,
        org_id=org_id,
        field_name="CURRENT_ORGANIZATION_ROLE",
        field_value="VP_SECURITY",
        source_id=src_pub.id,
        verification_method="WEB_SCRAPE",
        assurance_level=AssuranceLevel.LOW,
        disclosure_class=DisclosureClass.PUBLIC,
    )
    asst_fresh_idp = await prov.record_assertion(
        principal_id=principal.id,
        org_id=org_id,
        field_name="CURRENT_ORGANIZATION_ROLE",
        field_value="REMOVED",
        source_id=src_idp.id,
        verification_method="SCIM_ROLE_SYNC",
        assurance_level=AssuranceLevel.HIGH,
        disclosure_class=DisclosureClass.TENANT_INTERNAL,
    )

    conflict = await conflict_engine.record_conflict(
        principal_id=principal.id,
        org_id=org_id,
        field_or_claim="CURRENT_ORGANIZATION_ROLE",
        assertion_id_a=asst_old_pub.id,
        assertion_id_b=asst_fresh_idp.id,
    )

    status, reason = await conflict_engine.evaluate_and_resolve(conflict.id, org_id=org_id)
    assert status == ConflictStatus.RESOLVED_SUPERSEDED
    assert "Assertion B (TIER_C) is authoritative for CURRENT_ORGANIZATION_ROLE" in reason


@pytest.mark.asyncio
async def test_old_key_assertion_cannot_override_fresh_cryptographic_revocation(sqlite_engine):
    """Old key listing in directory cannot override fresh cryptographic revocation."""
    org_id = "org_acme_corp"
    dir_svc = PrincipalDirectory(sqlite_engine)
    prov = TrustProvenanceEngine(sqlite_engine)
    conflict_engine = TrustConflictEngine(sqlite_engine)

    principal = await dir_svc.create_principal(
        org_id=org_id, principal_type=PrincipalType.SERVICE, display_name="API Gateway"
    )

    src_dir = await prov.register_source(
        name="Enterprise_Wiki_Keylist",
        source_tier=SourceTier.TIER_E,
        provider_type="WIKI",
        org_id=org_id,
    )
    src_crypto = await prov.register_source(
        name="HSM_Revocation_Endpoint",
        source_tier=SourceTier.TIER_A,
        provider_type="CRYPTO_CHALLENGE",
        org_id=org_id,
    )

    asst_old_dir = await prov.record_assertion(
        principal_id=principal.id,
        org_id=org_id,
        field_name="KEY_POSSESSION",
        field_value="ed25519_pub_active",
        source_id=src_dir.id,
        verification_method="MANUAL_DOC",
        assurance_level=AssuranceLevel.LOW,
        disclosure_class=DisclosureClass.PUBLIC,
    )
    asst_fresh_crypto = await prov.record_assertion(
        principal_id=principal.id,
        org_id=org_id,
        field_name="KEY_POSSESSION",
        field_value="REVOKED",
        source_id=src_crypto.id,
        verification_method="CRL_HSM_CHECK",
        assurance_level=AssuranceLevel.CRYPTOGRAPHIC,
        disclosure_class=DisclosureClass.SECURITY_RESTRICTED,
    )

    conflict = await conflict_engine.record_conflict(
        principal_id=principal.id,
        org_id=org_id,
        field_or_claim="KEY_POSSESSION",
        assertion_id_a=asst_old_dir.id,
        assertion_id_b=asst_fresh_crypto.id,
    )

    status, reason = await conflict_engine.evaluate_and_resolve(conflict.id, org_id=org_id)
    assert status == ConflictStatus.RESOLVED_SUPERSEDED
    assert "Assertion B (TIER_A) is authoritative for KEY_POSSESSION" in reason


@pytest.mark.asyncio
async def test_old_agent_ownership_cannot_override_current_owner_change(sqlite_engine):
    """Old third-party owner claim cannot override current enterprise registry owner assignment."""
    org_id = "org_acme_corp"
    dir_svc = PrincipalDirectory(sqlite_engine)
    prov = TrustProvenanceEngine(sqlite_engine)
    conflict_engine = TrustConflictEngine(sqlite_engine)

    agent = await dir_svc.create_principal(
        org_id=org_id, principal_type=PrincipalType.AI_AGENT, display_name="Dev Agent"
    )

    src_third_party = await prov.register_source(
        name="External_Vendor_Catalog",
        source_tier=SourceTier.TIER_D,
        provider_type="PARTNER_CATALOG",
        org_id=org_id,
    )
    src_enterprise = await prov.register_source(
        name="Enterprise_Agent_Controller",
        source_tier=SourceTier.TIER_C,
        provider_type="INTERNAL_CONTROLLER",
        org_id=org_id,
    )

    asst_old_owner = await prov.record_assertion(
        principal_id=agent.id,
        org_id=org_id,
        field_name="AGENT_OWNERSHIP",
        field_value="external_vendor_llc",
        source_id=src_third_party.id,
        verification_method="PARTNER_API",
        assurance_level=AssuranceLevel.MEDIUM,
        disclosure_class=DisclosureClass.BUSINESS_PUBLIC,
    )
    asst_new_owner = await prov.record_assertion(
        principal_id=agent.id,
        org_id=org_id,
        field_name="AGENT_OWNERSHIP",
        field_value="acme_internal_engineering",
        source_id=src_enterprise.id,
        verification_method="INTERNAL_DISCOVERY",
        assurance_level=AssuranceLevel.HIGH,
        disclosure_class=DisclosureClass.TENANT_INTERNAL,
    )

    conflict = await conflict_engine.record_conflict(
        principal_id=agent.id,
        org_id=org_id,
        field_or_claim="AGENT_OWNERSHIP",
        assertion_id_a=asst_old_owner.id,
        assertion_id_b=asst_new_owner.id,
    )

    status, reason = await conflict_engine.evaluate_and_resolve(conflict.id, org_id=org_id)
    assert status == ConflictStatus.RESOLVED_SUPERSEDED
    assert "Assertion B (TIER_C) is authoritative for AGENT_OWNERSHIP" in reason
