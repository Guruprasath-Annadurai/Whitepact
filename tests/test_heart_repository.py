"""Persistence and tenant-isolation tests for Heart production records."""

from __future__ import annotations

import pytest

from responsibleai.db import (
    ConsentProofRepository,
    HeartRecordNotFoundError,
    PurposeBindingRepository,
    RootAuthorityRepository,
    create_engine,
)
from responsibleai.governance.consent_proof import ConsentMethod, build_consent_proof
from responsibleai.governance.purpose_binding import build_purpose_binding
from responsibleai.governance.root_authority import RootType, build_root_authority_record


@pytest.fixture()
async def repositories():
    engine = create_engine(":memory:")
    await engine.init()
    yield (
        RootAuthorityRepository(engine),
        ConsentProofRepository(engine),
        PurposeBindingRepository(engine),
    )
    await engine.close()


async def test_root_round_trip_and_tenant_isolation(repositories) -> None:
    roots, _consents, _bindings = repositories
    root = build_root_authority_record(
        "principal-1",
        RootType.ORGANIZATION,
        "org-repository",
        "api-key-hash",
        organization_id="org-1",
        evidence_refs=("verification-1",),
    )
    await roots.issue("org-1", root)

    assert await roots.get("org-1", root.root_id) == root
    assert await roots.get("org-2", root.root_id) is None


async def test_root_chain_never_crosses_tenants(repositories) -> None:
    roots, _consents, _bindings = repositories
    parent = build_root_authority_record(
        "org-parent",
        RootType.ORGANIZATION,
        "issuer",
        "method",
        organization_id="org-2",
    )
    child = build_root_authority_record(
        "service",
        RootType.SERVICE_PRINCIPAL,
        "issuer",
        "method",
        organization_id="org-1",
        authority_source=parent.root_id,
    )
    await roots.issue("org-2", parent)
    await roots.issue("org-1", child)

    chain = await roots.load_chain("org-1", child)
    assert set(chain) == {child.root_id}


async def test_consent_and_binding_round_trip(repositories) -> None:
    _roots, consents, bindings = repositories
    proof = build_consent_proof(
        "principal-1",
        "root-1",
        "principal-1",
        "Use governance tools",
        "govern models",
        ConsentMethod.API_AUTHENTICATED_REQUEST,
        evidence_refs=("request-1",),
    )
    binding = build_purpose_binding("govern models", "intent-1", proof.consent_id)

    await consents.issue("org-1", proof)
    await bindings.bind("org-1", "principal-1", binding)

    assert await consents.get("org-1", proof.consent_id) == proof
    assert (
        await bindings.get_for_refs("org-1", "principal-1", "intent-1", proof.consent_id) == binding
    )
    assert await consents.get("org-2", proof.consent_id) is None


async def test_revocation_is_atomic_and_cannot_be_replayed(repositories) -> None:
    roots, _consents, _bindings = repositories
    root = build_root_authority_record(
        "principal-1",
        RootType.ORGANIZATION,
        "issuer",
        "method",
        organization_id="org-1",
    )
    await roots.issue("org-1", root)

    revoked = await roots.revoke("org-1", root.root_id, revoked_by="admin-1")
    assert revoked.revoked_at is not None
    with pytest.raises(HeartRecordNotFoundError):
        await roots.revoke("org-1", root.root_id, revoked_by="admin-2")
