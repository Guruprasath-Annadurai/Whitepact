# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit and adversarial tests for Trust Fabric Privacy Boundaries & Anti-Enumeration."""

from __future__ import annotations

import pytest

from responsibleai.db.engine import (
    create_engine,
    organizations,
)
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import (
    AssuranceLevel,
    DisclosureClass,
    IdentifierType,
    IdentifierVerificationState,
    PrincipalType,
    SourceTier,
)
from responsibleai.trust_fabric.errors import (
    CrossTenantAccessError,
)
from responsibleai.trust_fabric.passport import TrustPassportEngine
from responsibleai.trust_fabric.provenance import TrustProvenanceEngine


@pytest.fixture
async def privacy_db(tmp_path):
    url = f"{tmp_path}/test_privacy.db"
    engine = create_engine(url)
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert(),
            [
                {"id": "org_privacy_a", "name": "Company A", "slug": "compa", "created_at": "now"},
                {"id": "org_privacy_b", "name": "Company B", "slug": "compb", "created_at": "now"},
            ],
        )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_anti_enumeration_cross_tenant_query(privacy_db):
    """Querying an identifier belonging to Company A from Company B returns not found (zero leakage)."""
    dir_svc = PrincipalDirectory(privacy_db)

    # Alice belongs to Company A
    alice = await dir_svc.create_principal(
        org_id="org_privacy_a",
        principal_type=PrincipalType.HUMAN,
        display_name="Alice Private",
    )
    await dir_svc.attach_identifier(
        principal_id=alice.id,
        org_id="org_privacy_a",
        identifier_type=IdentifierType.EMAIL,
        value="alice@comp-a.internal",
        verification_state=IdentifierVerificationState.VERIFIED,
    )

    # Attacker from Company B attempts to look up Alice's identifier under Company B
    res_b = await dir_svc.resolve_by_identifier(
        org_id="org_privacy_b",
        identifier_type=IdentifierType.EMAIL,
        value="alice@comp-a.internal",
    )
    # Must be None, identical to looking up a non-existent identifier
    assert res_b is None

    # Cross-tenant get_principal by ID must raise CrossTenantAccessError
    with pytest.raises(CrossTenantAccessError):
        await dir_svc.get_principal(alice.id, org_id="org_privacy_b")


@pytest.mark.asyncio
async def test_selective_disclosure_filters_sensitive_pii(privacy_db):
    """Public and Business Public views strictly redact personal PII."""
    dir_svc = PrincipalDirectory(privacy_db)
    prov_svc = TrustProvenanceEngine(privacy_db)
    pass_svc = TrustPassportEngine(privacy_db)

    src = await prov_svc.register_source(
        name="HR System",
        source_tier=SourceTier.TIER_C,
        provider_type="WORKDAY",
        org_id="org_privacy_a",
    )

    alice = await dir_svc.create_principal(
        org_id="org_privacy_a",
        principal_type=PrincipalType.HUMAN,
        display_name="Alice Architect",
    )

    await prov_svc.record_assertion(
        principal_id=alice.id,
        org_id="org_privacy_a",
        field_name="job_title",
        field_value="Security Architect",
        source_id=src.id,
        verification_method="HR_ONBOARDING",
        assurance_level=AssuranceLevel.HIGH,
        disclosure_class=DisclosureClass.PUBLIC,
    )
    await prov_svc.record_assertion(
        principal_id=alice.id,
        org_id="org_privacy_a",
        field_name="work_email",
        field_value="alice@compa.com",
        source_id=src.id,
        verification_method="HR_ONBOARDING",
        assurance_level=AssuranceLevel.HIGH,
        disclosure_class=DisclosureClass.BUSINESS_PUBLIC,
    )
    await prov_svc.record_assertion(
        principal_id=alice.id,
        org_id="org_privacy_a",
        field_name="residential_address",
        field_value="123 Secret Lane, Metropolis",
        source_id=src.id,
        verification_method="HR_ONBOARDING",
        assurance_level=AssuranceLevel.MEDIUM,
        disclosure_class=DisclosureClass.TENANT_INTERNAL,
    )
    await prov_svc.record_assertion(
        principal_id=alice.id,
        org_id="org_privacy_a",
        field_name="ssn",
        field_value="000-12-3456",
        source_id=src.id,
        verification_method="GOV_ID",
        assurance_level=AssuranceLevel.HIGH,
        disclosure_class=DisclosureClass.SECURITY_RESTRICTED,
    )

    passport = await pass_svc.generate_passport(principal_id=alice.id, org_id="org_privacy_a")

    # 1. PUBLIC view
    pub_view = pass_svc.filter_selective_disclosure(passport, audience_view=DisclosureClass.PUBLIC)
    attrs_pub = pub_view["disclosed_attributes"]
    assert "job_title" in attrs_pub
    assert "work_email" not in attrs_pub
    assert "residential_address" not in attrs_pub
    assert "ssn" not in attrs_pub

    # 2. BUSINESS_PUBLIC view
    biz_view = pass_svc.filter_selective_disclosure(
        passport, audience_view=DisclosureClass.BUSINESS_PUBLIC
    )
    attrs_biz = biz_view["disclosed_attributes"]
    assert "job_title" in attrs_biz
    assert "work_email" in attrs_biz
    assert "residential_address" not in attrs_biz
    assert "ssn" not in attrs_biz

    # 3. TENANT_INTERNAL view
    internal_view = pass_svc.filter_selective_disclosure(
        passport, audience_view=DisclosureClass.TENANT_INTERNAL
    )
    attrs_int = internal_view["disclosed_attributes"]
    assert "residential_address" in attrs_int
    assert "ssn" not in attrs_int

    # 4. SECURITY_RESTRICTED view
    sec_view = pass_svc.filter_selective_disclosure(
        passport, audience_view=DisclosureClass.SECURITY_RESTRICTED
    )
    attrs_sec = sec_view["disclosed_attributes"]
    assert "ssn" in attrs_sec


@pytest.mark.asyncio
async def test_no_universal_reputation_scoring(privacy_db):
    """Assurance is factual, multidimensional vectors, rejecting universal reputation/social credit score."""
    dir_svc = PrincipalDirectory(privacy_db)
    prov_svc = TrustProvenanceEngine(privacy_db)

    p = await dir_svc.create_principal(
        org_id="org_privacy_a",
        principal_type=PrincipalType.AI_AGENT,
        display_name="Deployment Agent",
    )

    vector = await prov_svc.evaluate_assurance_vector(p.id, org_id="org_privacy_a")
    # Verify no scalar reputation score exists
    assert not hasattr(vector, "score")
    assert not hasattr(vector, "reputation")
    assert not hasattr(vector, "credit_score")

    # Has factual categorical assurances
    assert vector.identity_assurance.value in ["LOW", "MEDIUM", "HIGH", "CRYPTOGRAPHIC"]
    assert vector.affiliation_assurance.value in ["LOW", "MEDIUM", "HIGH", "CRYPTOGRAPHIC"]
    assert vector.authority_assurance.value in ["LOW", "MEDIUM", "HIGH", "CRYPTOGRAPHIC"]
