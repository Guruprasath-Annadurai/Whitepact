# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial tests for Trust Passport & Selective Disclosure."""

from __future__ import annotations

from dataclasses import replace

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import (
    AssuranceLevel,
    DisclosureClass,
    PrincipalType,
    SourceTier,
)
from responsibleai.trust_fabric.errors import TrustPassportTamperedError
from responsibleai.trust_fabric.passport import TrustPassportEngine
from responsibleai.trust_fabric.provenance import TrustProvenanceEngine


@pytest.fixture
async def passport_db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path}/test_pass.db"
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
class TestTrustPassport:
    async def test_generate_and_verify_passport_integrity(self, passport_db):
        dir_svc = PrincipalDirectory(passport_db)
        prov_svc = TrustProvenanceEngine(passport_db)
        pass_svc = TrustPassportEngine(passport_db)

        # 1. Register principal and source
        src = await prov_svc.register_source(
            name="HR Enterprise System",
            source_tier=SourceTier.TIER_C,
            provider_type="WORKDAY",
            org_id="org_corp",
        )
        alice = await dir_svc.create_principal(
            org_id="org_corp",
            principal_type=PrincipalType.HUMAN,
            display_name="Alice Senior VP",
        )
        # Record public role and private confidential field
        await prov_svc.record_assertion(
            principal_id=alice.id,
            org_id="org_corp",
            field_name="title",
            field_value="Vice President of Engineering",
            source_id=src.id,
            verification_method="SAML_SSO",
            assurance_level=AssuranceLevel.HIGH,
            disclosure_class=DisclosureClass.PUBLIC,
        )
        await prov_svc.record_assertion(
            principal_id=alice.id,
            org_id="org_corp",
            field_name="residential_address",
            field_value="123 Private Street, Hidden City",
            source_id=src.id,
            verification_method="HR_ONBOARDING",
            assurance_level=AssuranceLevel.MEDIUM,
            disclosure_class=DisclosureClass.TENANT_INTERNAL,
        )

        # 2. Generate passport
        passport = await pass_svc.generate_passport(
            principal_id=alice.id,
            org_id="org_corp",
            signing_key_id="key_prod_1",
        )

        assert passport.passport_type == PrincipalType.HUMAN
        assert passport.is_valid is True
        assert pass_svc.verify_passport_integrity(passport) is True

        # 3. Tamper attack: modify claims
        tampered_claims = dict(passport.claims)
        tampered_claims["display_name"] = "Alice CEO (Forged)"
        tampered_passport = replace(passport, claims=tampered_claims)

        with pytest.raises(TrustPassportTamperedError):
            pass_svc.verify_passport_integrity(tampered_passport)

        # 4. Tamper attack: modify assurance vector
        tampered_assurance = replace(passport.assurance, identity_assurance=AssuranceLevel.CRYPTOGRAPHIC)
        tampered_passport2 = replace(passport, assurance=tampered_assurance)

        with pytest.raises(TrustPassportTamperedError):
            pass_svc.verify_passport_integrity(tampered_passport2)

    async def test_selective_disclosure_privacy_boundary(self, passport_db):
        dir_svc = PrincipalDirectory(passport_db)
        prov_svc = TrustProvenanceEngine(passport_db)
        pass_svc = TrustPassportEngine(passport_db)

        src = await prov_svc.register_source(
            name="HR System", source_tier=SourceTier.TIER_C, provider_type="IDP", org_id="org_corp"
        )
        alice = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Alice VP"
        )

        await prov_svc.record_assertion(
            principal_id=alice.id,
            org_id="org_corp",
            field_name="public_role",
            field_value="Procurement Officer",
            source_id=src.id,
            verification_method="IDP",
            assurance_level=AssuranceLevel.HIGH,
            disclosure_class=DisclosureClass.PUBLIC,
        )
        await prov_svc.record_assertion(
            principal_id=alice.id,
            org_id="org_corp",
            field_name="personal_phone",
            field_value="+1-555-987-6543",
            source_id=src.id,
            verification_method="CONSENTED_HR",
            assurance_level=AssuranceLevel.HIGH,
            disclosure_class=DisclosureClass.TENANT_INTERNAL,
        )

        passport = await pass_svc.generate_passport(principal_id=alice.id, org_id="org_corp")

        # PUBLIC disclosure view
        public_view = pass_svc.filter_selective_disclosure(passport, audience_view=DisclosureClass.PUBLIC)
        assert "public_role" in public_view["disclosed_attributes"]
        assert "personal_phone" not in public_view["disclosed_attributes"]

        # TENANT_INTERNAL view contains internal fields
        internal_view = pass_svc.filter_selective_disclosure(
            passport, audience_view=DisclosureClass.TENANT_INTERNAL
        )
        assert "public_role" in internal_view["disclosed_attributes"]
        assert "personal_phone" in internal_view["disclosed_attributes"]
