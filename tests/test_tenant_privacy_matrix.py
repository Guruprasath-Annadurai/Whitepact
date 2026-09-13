# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit and adversarial tests for Tenant Isolation & Privacy Disclosure Matrix (Sections 9 & 10)."""

from __future__ import annotations

import pytest

from responsibleai.db.engine import (
    create_engine,
    organizations,
)
from responsibleai.trust_fabric.authority_graph import AuthorityGraph
from responsibleai.trust_fabric.decision import TrustDecisionEngine
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import (
    AssuranceLevel,
    DecisionOutcome,
    DisclosureClass,
    IdentifierType,
    PrincipalType,
    SourceTier,
)
from responsibleai.trust_fabric.errors import CrossTenantAccessError
from responsibleai.trust_fabric.models import (
    TrustDecisionRequest,
)
from responsibleai.trust_fabric.passport import TrustPassportEngine
from responsibleai.trust_fabric.provenance import TrustProvenanceEngine


@pytest.fixture
async def tenant_db(tmp_path):
    url = f"{tmp_path}/test_tenant_matrix.db"
    engine = create_engine(url)
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert(),
            [
                {"id": "org_alpha", "name": "Tenant Alpha", "slug": "alpha", "created_at": "now"},
                {"id": "org_beta", "name": "Tenant Beta", "slug": "beta", "created_at": "now"},
            ],
        )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_cross_tenant_isolation_matrix(tenant_db):
    """Empirically test every cross-tenant mutation and access path: UNAUTHORIZED SUCCESSES: 0."""
    dir_svc = PrincipalDirectory(tenant_db)
    auth_graph = AuthorityGraph(tenant_db)
    pass_engine = TrustPassportEngine(tenant_db)
    dec_engine = TrustDecisionEngine(tenant_db)

    # 1. Setup Alpha principals
    alpha_root = await dir_svc.create_principal(
        org_id="org_alpha",
        principal_type=PrincipalType.ORGANIZATION,
        display_name="Alpha Root",
    )
    alpha_user = await dir_svc.create_principal(
        org_id="org_alpha",
        principal_type=PrincipalType.HUMAN,
        display_name="Alpha User",
    )

    unauthorized_successes = 0

    # 1. Cross-tenant principal read
    try:
        await dir_svc.get_principal(alpha_user.id, org_id="org_beta")
        unauthorized_successes += 1
    except CrossTenantAccessError:
        pass

    # 2. Cross-tenant principal delete / mutate
    try:
        await dir_svc.delete_principal(alpha_user.id, org_id="org_beta")
        unauthorized_successes += 1
    except CrossTenantAccessError:
        pass

    # 3. Cross-tenant identifier attach
    try:
        await dir_svc.attach_identifier(
            principal_id=alpha_user.id,
            org_id="org_beta",
            identifier_type=IdentifierType.EMAIL,
            value="hacked@beta.com",
        )
        unauthorized_successes += 1
    except CrossTenantAccessError:
        pass

    # 4. Cross-tenant relationship creation
    try:
        await auth_graph.create_relationship(
            org_id="org_beta",
            subject_principal_id=alpha_user.id,
            target_principal_id=alpha_root.id,
            relationship_type="EMPLOYED_BY",
            source_id="src_fake",
        )
        unauthorized_successes += 1
    except CrossTenantAccessError:
        pass

    # 5. Cross-tenant authority creation
    try:
        await auth_graph.grant_authority(
            grantor_principal_id=alpha_root.id,
            grantee_principal_id=alpha_user.id,
            org_id="org_beta",
            action_type="SIGN_PAYMENT",
            resource_pattern="*",
        )
        unauthorized_successes += 1
    except CrossTenantAccessError:
        pass

    # 6. Cross-tenant passport generation
    try:
        await pass_engine.generate_passport(
            principal_id=alpha_user.id,
            org_id="org_beta",
        )
        unauthorized_successes += 1
    except CrossTenantAccessError:
        pass

    # 7. Cross-tenant Trust Decision (Beta requesting decision on Alpha target)
    req_cross = TrustDecisionRequest(
        requesting_org_id="org_beta",
        target_org_id="org_beta",
        subject_principal_id=alpha_user.id,
        requested_action="TRANSFER",
    )
    resp_cross = await dec_engine.evaluate_decision(req_cross)
    assert resp_cross.decision == DecisionOutcome.DENY
    assert resp_cross.reason_code == "CROSS_TENANT_DISALLOWED"

    assert unauthorized_successes == 0


@pytest.mark.asyncio
async def test_privacy_disclosure_matrix_and_regulatory_overclaim_removal(tenant_db):
    """Empirically test selective disclosure across all views and verify regulatory overclaim removal."""
    dir_svc = PrincipalDirectory(tenant_db)
    prov_svc = TrustProvenanceEngine(tenant_db)
    pass_engine = TrustPassportEngine(tenant_db)

    # Create Alpha source
    src = await prov_svc.register_source(
        org_id="org_alpha",
        name="Alpha Identity Provider",
        source_tier=SourceTier.TIER_C,
        provider_type="HR_SYSTEM",
    )

    # Create principal
    user = await dir_svc.create_principal(
        org_id="org_alpha",
        principal_type=PrincipalType.HUMAN,
        display_name="Eve Employee",
    )

    # Record assertions across all disclosure classes
    assertions = [
        # Public
        ("job_title", "Senior Systems Architect", DisclosureClass.PUBLIC),
        # Business public
        ("work_email", "eve@alpha.com", DisclosureClass.BUSINESS_PUBLIC),
        # Tenant internal
        ("employee_id", "EMP-98765", DisclosureClass.TENANT_INTERNAL),
        # Private dossier fields (NEVER_PUBLIC / confidential)
        ("private_phone", "+15550001111", DisclosureClass.TENANT_INTERNAL),
        ("private_email", "eve.personal@gmail.com", DisclosureClass.TENANT_INTERNAL),
        ("private_address", "123 Secret Lane, City", DisclosureClass.TENANT_INTERNAL),
        # Security restricted
        ("security_restricted_identifier", "TOKEN_RESTRICTED_XYZ", DisclosureClass.SECURITY_RESTRICTED),
        # Internal credential metadata
        ("internal_credential_metadata", "CRED_HASH_ABC123", DisclosureClass.NEVER_PUBLIC),
    ]

    for fname, fval, fdisc in assertions:
        await prov_svc.record_assertion(
            principal_id=user.id,
            org_id="org_alpha",
            field_name=fname,
            field_value=fval,
            source_id=src.id,
            verification_method="OAUTH_HRIS",
            assurance_level=AssuranceLevel.HIGH,
            disclosure_class=fdisc,
        )

    # Generate passport
    passport = await pass_engine.generate_passport(
        principal_id=user.id,
        org_id="org_alpha",
    )

    unauthorized_disclosures = 0

    # 1. PUBLIC VIEW
    view_public = pass_engine.filter_selective_disclosure(
        passport, audience_view=DisclosureClass.PUBLIC
    )
    attrs_pub = view_public["disclosed_attributes"]
    assert "job_title" in attrs_pub
    assert "work_email" not in attrs_pub  # Business public, not public
    assert "employee_id" not in attrs_pub
    for sensitive in ("private_phone", "private_email", "private_address", "security_restricted_identifier", "internal_credential_metadata"):
        if sensitive in attrs_pub:
            unauthorized_disclosures += 1
    assert "disclaimer" not in view_public
    assert view_public["regulatory_compliance_claimed"] is False

    # 2. BUSINESS VIEW (BUSINESS_PUBLIC)
    view_biz = pass_engine.filter_selective_disclosure(
        passport, audience_view=DisclosureClass.BUSINESS_PUBLIC
    )
    attrs_biz = view_biz["disclosed_attributes"]
    assert "job_title" in attrs_biz
    assert "work_email" in attrs_biz
    assert "employee_id" not in attrs_biz
    for sensitive in ("private_phone", "private_email", "private_address", "security_restricted_identifier", "internal_credential_metadata"):
        if sensitive in attrs_biz:
            unauthorized_disclosures += 1
    assert view_biz["regulatory_compliance_claimed"] is False

    # 3. TENANT INTERNAL VIEW
    view_internal = pass_engine.filter_selective_disclosure(
        passport, audience_view=DisclosureClass.TENANT_INTERNAL
    )
    attrs_int = view_internal["disclosed_attributes"]
    assert "job_title" in attrs_int
    assert "work_email" in attrs_int
    assert "employee_id" in attrs_int
    # Security restricted and never public MUST NOT leak into tenant internal
    if "security_restricted_identifier" in attrs_int or "internal_credential_metadata" in attrs_int:
        unauthorized_disclosures += 1
    assert view_internal["regulatory_compliance_claimed"] is False

    # 4. PRIVILEGED AUDIT VIEW (Section 10)
    view_audit = pass_engine.filter_selective_disclosure(
        passport, audience_view=DisclosureClass.PRIVILEGED_AUDIT_VIEW
    )
    assert view_audit["disclaimer"] == "This view does not establish regulatory compliance."
    assert view_audit["regulatory_compliance_claimed"] is False

    assert unauthorized_disclosures == 0
