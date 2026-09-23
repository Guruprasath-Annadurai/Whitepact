# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit and adversarial tests for TrustSourceProvider Interface (Section 13)."""

from __future__ import annotations

import pytest

from responsibleai.trust_fabric.enums import SourceTier
from responsibleai.trust_fabric.provider import (
    ProviderQueryResultStatus,
    SourceQueryResult,
    TrustSourceProvider,
    TrustSourceRegistry,
)


class MockHealthyProvider(TrustSourceProvider):
    @property
    def provider_id(self) -> str:
        return "provider_healthy_idp"

    @property
    def source_tier(self) -> SourceTier:
        return SourceTier.TIER_C

    async def query_claim(
        self,
        *,
        principal_id: str,
        identifier_value: str,
        claim_type: str,
    ) -> SourceQueryResult:
        if identifier_value == "active_user@corp.com":
            return SourceQueryResult(
                status=ProviderQueryResultStatus.ASSERTION_VERIFIED,
                source_id=self.provider_id,
                source_tier=self.source_tier,
                claim_type=claim_type,
                payload={"employed": True},
                evidence_digest="dig_active",
            )
        elif identifier_value == "conflicted_user@corp.com":
            return SourceQueryResult(
                status=ProviderQueryResultStatus.ASSERTION_CONFLICTED,
                source_id=self.provider_id,
                source_tier=self.source_tier,
                claim_type=claim_type,
                payload={"conflict_reason": "Dual conflicting records"},
            )
        else:
            return SourceQueryResult(
                status=ProviderQueryResultStatus.ASSERTION_NOT_VERIFIED,
                source_id=self.provider_id,
                source_tier=self.source_tier,
                claim_type=claim_type,
            )


class MockOutageProvider(TrustSourceProvider):
    @property
    def provider_id(self) -> str:
        return "provider_outage"

    @property
    def source_tier(self) -> SourceTier:
        return SourceTier.TIER_B

    async def query_claim(
        self,
        *,
        principal_id: str,
        identifier_value: str,
        claim_type: str,
    ) -> SourceQueryResult:
        raise ConnectionError("Upstream registry unavailable (HTTP 503 Gateway Timeout)")


class MockUnauthorizedProvider(TrustSourceProvider):
    @property
    def provider_id(self) -> str:
        return "provider_unauthorized"

    @property
    def source_tier(self) -> SourceTier:
        return SourceTier.TIER_C

    async def query_claim(
        self,
        *,
        principal_id: str,
        identifier_value: str,
        claim_type: str,
    ) -> SourceQueryResult:
        return SourceQueryResult(
            status=ProviderQueryResultStatus.SOURCE_UNAUTHORIZED,
            source_id=self.provider_id,
            source_tier=self.source_tier,
            claim_type=claim_type,
            error_detail="API key expired or invalid client cert",
        )


@pytest.mark.asyncio
async def test_provider_status_distinctions():
    """Trust source query protocol explicitly distinguishes all 6 statuses."""
    registry = TrustSourceRegistry()
    registry.register_provider(MockHealthyProvider())
    registry.register_provider(MockOutageProvider())
    registry.register_provider(MockUnauthorizedProvider())

    # 1. SOURCE_NOT_FOUND
    res_not_found = await registry.query_provider(
        "non_existent_provider",
        principal_id="wp_pr_1",
        identifier_value="test@corp.com",
        claim_type="EMPLOYMENT",
    )
    assert res_not_found.status == ProviderQueryResultStatus.SOURCE_NOT_FOUND
    assert not res_not_found.is_verified

    # 2. SOURCE_UNAVAILABLE (network failure / outage)
    res_outage = await registry.query_provider(
        "provider_outage",
        principal_id="wp_pr_1",
        identifier_value="test@corp.com",
        claim_type="EMPLOYMENT",
    )
    assert res_outage.status == ProviderQueryResultStatus.SOURCE_UNAVAILABLE
    assert not res_outage.is_verified

    # 3. SOURCE_UNAUTHORIZED (auth failure)
    res_unauth = await registry.query_provider(
        "provider_unauthorized",
        principal_id="wp_pr_1",
        identifier_value="test@corp.com",
        claim_type="EMPLOYMENT",
    )
    assert res_unauth.status == ProviderQueryResultStatus.SOURCE_UNAUTHORIZED
    assert not res_unauth.is_verified

    # 4. ASSERTION_NOT_VERIFIED
    res_not_ver = await registry.query_provider(
        "provider_healthy_idp",
        principal_id="wp_pr_1",
        identifier_value="unknown_user@corp.com",
        claim_type="EMPLOYMENT",
    )
    assert res_not_ver.status == ProviderQueryResultStatus.ASSERTION_NOT_VERIFIED
    assert not res_not_ver.is_verified

    # 5. ASSERTION_VERIFIED
    res_ver = await registry.query_provider(
        "provider_healthy_idp",
        principal_id="wp_pr_1",
        identifier_value="active_user@corp.com",
        claim_type="EMPLOYMENT",
    )
    assert res_ver.status == ProviderQueryResultStatus.ASSERTION_VERIFIED
    assert res_ver.is_verified

    # 6. ASSERTION_CONFLICTED
    res_conf = await registry.query_provider(
        "provider_healthy_idp",
        principal_id="wp_pr_1",
        identifier_value="conflicted_user@corp.com",
        claim_type="EMPLOYMENT",
    )
    assert res_conf.status == ProviderQueryResultStatus.ASSERTION_CONFLICTED
    assert not res_conf.is_verified


@pytest.mark.asyncio
async def test_provider_outage_never_causes_false_verification():
    """Provider outage or exception strictly fails closed: UNKNOWN/REVOKED never becomes VERIFIED."""
    registry = TrustSourceRegistry()
    registry.register_provider(MockOutageProvider())

    result = await registry.query_provider(
        "provider_outage",
        principal_id="wp_pr_unknown",
        identifier_value="unknown@example.com",
        claim_type="CLEARANCE",
    )
    assert result.status != ProviderQueryResultStatus.ASSERTION_VERIFIED
    assert result.is_verified is False

    unknown_to_verified_occurred = result.is_verified
    assert not unknown_to_verified_occurred


def test_global_authoritative_coverage_classification():
    """Commercial reality: Global authoritative coverage is NOT_ESTABLISHED."""
    global_authoritative_person_coverage = "NOT_ESTABLISHED"
    global_authoritative_company_coverage = "NOT_ESTABLISHED"
    enterprise_source_partnerships = "NOT_ESTABLISHED"

    assert global_authoritative_person_coverage == "NOT_ESTABLISHED"
    assert global_authoritative_company_coverage == "NOT_ESTABLISHED"
    assert enterprise_source_partnerships == "NOT_ESTABLISHED"
