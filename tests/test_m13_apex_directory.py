# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Repository metadata/tenant regressions, not customer authority acceptance."""

import asyncio

import pytest

from responsibleai.db.engine import create_engine, organizations
from responsibleai.trust_fabric.directory import PrincipalDirectory, normalize_identifier
from responsibleai.trust_fabric.enums import IdentifierType, PrincipalType
from responsibleai.trust_fabric.errors import (
    CrossTenantAccessError,
    IdentifierCollisionError,
    PrincipalInactiveError,
)
from tests.test_stage3_controller_postgres import controller as controller


@pytest.fixture(params=["sqlite", "postgres"])
async def directory(request, tmp_path, controller):
    async def prepare(url):
        engine = create_engine(url)
        if request.param == "sqlite":
            await engine.init()
        async with engine.raw.begin() as connection:
            await connection.execute(
                organizations.insert(),
                [
                    {"id": "apex-org", "name": "APEX", "slug": "apex", "created_at": "now"},
                    {"id": "other-org", "name": "Other", "slug": "other", "created_at": "now"},
                ],
            )
        return engine

    if request.param == "postgres":
        service, _, _, token, csrf = controller
        tenant_ids = {}
        for label, name, slug in (("apex-org", "APEX", "apex"), ("other-org", "Other", "other")):
            tenant_ids[label] = await service.create(
                session_token=token,
                csrf=csrf,
                request_id=f"directory-{label}",
                name=name,
                slug=slug,
            )
            lifecycle = service.provider.get_state(tenant_ids[label])
            completion = service.ledger.completion(tenant_ids[label])
            assert lifecycle.state.value == "ACTIVE"
            assert completion.generation_id == lifecycle.generation_id
        directory = PrincipalDirectory(service.engine)
        directory.fixture_tenant_ids = tenant_ids
        yield directory
    else:
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path}/directory.db")
        try:
            directory = PrincipalDirectory(engine)
            directory.fixture_tenant_ids = {"apex-org": "apex-org", "other-org": "other-org"}
            yield directory
        finally:
            await engine.close()


@pytest.mark.asyncio
async def test_metadata_survives_all_directory_read_paths(directory):
    own, other = (directory.fixture_tenant_ids[label] for label in ("apex-org", "other-org"))
    metadata = {"environment": "local", "labels": ["customer-created"]}
    principal = await directory.create_principal(
        org_id=own,
        principal_type=PrincipalType.AI_AGENT,
        display_name="APEX descriptive agent",
        metadata=metadata,
    )
    await directory.attach_identifier(
        org_id=own,
        principal_id=principal.id,
        identifier_type=IdentifierType.EMAIL,
        value="apex@example.com",
    )
    direct = await directory.get_principal(principal.id, org_id=own)
    resolved = await directory.resolve_by_identifier(
        org_id=own, identifier_type=IdentifierType.EMAIL, value="APEX@EXAMPLE.COM"
    )
    searched = await directory.search_principals(org_id=own, query="descriptive")
    assert direct.metadata == metadata
    assert resolved is not None and resolved.metadata == metadata
    assert len(searched) == 1 and searched[0].metadata == metadata
    with pytest.raises(CrossTenantAccessError):
        await directory.get_principal(principal.id, org_id=other)
    assert await directory.search_principals(org_id=other, query="descriptive") == []


@pytest.mark.asyncio
async def test_concurrent_identifier_claim_has_one_winner_without_authority_transfer(directory):
    own = directory.fixture_tenant_ids["apex-org"]
    principals = [
        await directory.create_principal(
            org_id=own, principal_type=PrincipalType.AI_AGENT, display_name=f"Agent {index}"
        )
        for index in range(4)
    ]
    claims = await asyncio.gather(
        *[
            directory.attach_identifier(
                org_id=own,
                principal_id=principal.id,
                identifier_type=IdentifierType.EMAIL,
                value="same@example.com",
            )
            for principal in principals
        ],
        return_exceptions=True,
    )
    assert sum(not isinstance(item, Exception) for item in claims) == 1
    assert sum(isinstance(item, IdentifierCollisionError) for item in claims) == 3
    resolved = await directory.resolve_by_identifier(
        org_id=own, identifier_type=IdentifierType.EMAIL, value="same@example.com"
    )
    assert resolved is not None
    assert resolved.lifecycle_state.value == "PENDING_VERIFICATION"


@pytest.mark.parametrize(
    "kind,value",
    [
        (IdentifierType.EMAIL, "a@@example.com"),
        (IdentifierType.DOMAIN, "https:///"),
        (IdentifierType.PHONE, "+"),
        (IdentifierType.PHONE, "call me"),
        (IdentifierType.REGISTRATION_NUMBER, "   "),
    ],
)
def test_empty_or_malformed_identifiers_are_not_canonical_claims(kind, value):
    with pytest.raises(ValueError):
        normalize_identifier(kind, value)


@pytest.mark.asyncio
async def test_unicode_recycling_and_cross_tenant_claims_transfer_no_state(directory):
    own, other = (directory.fixture_tenant_ids[label] for label in ("apex-org", "other-org"))
    original = await directory.create_principal(
        org_id=own,
        principal_type=PrincipalType.HUMAN,
        display_name="Original",
        metadata={"descriptive_only": "old"},
    )
    await directory.attach_identifier(
        org_id=own,
        principal_id=original.id,
        identifier_type=IdentifierType.EMAIL,
        value="Ａlice@bücher.example",
    )
    resolved = await directory.resolve_by_identifier(
        org_id=own,
        identifier_type=IdentifierType.EMAIL,
        value="alice@xn--bcher-kva.example",
    )
    assert resolved is not None and resolved.id == original.id
    with pytest.raises(CrossTenantAccessError):
        await directory.delete_principal(original.id, org_id=other)
    await directory.delete_principal(original.id, org_id=own)
    assert (
        await directory.resolve_by_identifier(
            org_id=own,
            identifier_type=IdentifierType.EMAIL,
            value="alice@bücher.example",
        )
        is None
    )
    with pytest.raises(PrincipalInactiveError):
        await directory.attach_identifier(
            org_id=own,
            principal_id=original.id,
            identifier_type=IdentifierType.DOMAIN,
            value="example.com",
        )
    for org in (own, other):
        replacement = await directory.create_principal(
            org_id=org,
            principal_type=PrincipalType.HUMAN,
            display_name="Replacement",
        )
        binding = await directory.attach_identifier(
            org_id=org,
            principal_id=replacement.id,
            identifier_type=IdentifierType.EMAIL,
            value="alice@bücher.example",
        )
        assert replacement.id != original.id
        assert replacement.metadata == {}
        assert replacement.lifecycle_state.value == "PENDING_VERIFICATION"
        assert binding.verification_state.value == "UNVERIFIED"
