# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from responsibleai.db.engine import create_engine
from responsibleai.global_directory.enums import EvidenceState, PersonResolutionStatus
from responsibleai.global_directory.repository import GlobalDirectoryRepository
from responsibleai.global_directory.service import GlobalDirectoryService


@pytest.fixture
async def gd_service():
    engine = create_engine(":memory:")
    await engine.init()
    svc = GlobalDirectoryService(GlobalDirectoryRepository(engine))
    yield svc
    await engine.close()


@pytest.mark.asyncio
async def test_unique_person_resolved(gd_service: GlobalDirectoryService) -> None:
    payload = await gd_service.resolve_person("Arun Dev")
    assert payload.resolution == PersonResolutionStatus.RESOLVED.value
    assert payload.entity is not None
    assert payload.entity["canonical_name"] == "Arun Dev"


@pytest.mark.asyncio
async def test_common_name_ambiguous(gd_service: GlobalDirectoryService) -> None:
    payload = await gd_service.resolve_person("Ramesh")
    assert payload.resolution == PersonResolutionStatus.AMBIGUOUS.value
    assert len(payload.candidates) >= 3


@pytest.mark.asyncio
async def test_context_qualified_resolved(gd_service: GlobalDirectoryService) -> None:
    payload = await gd_service.resolve_person("Ramesh Kumar from Company A")
    assert payload.resolution == PersonResolutionStatus.RESOLVED.value
    assert payload.entity is not None
    assert "Ramesh Kumar" in payload.entity["canonical_name"]


@pytest.mark.asyncio
async def test_unknown_person(gd_service: GlobalDirectoryService) -> None:
    payload = await gd_service.resolve_person("Zyxnonexistent Qwerty Person")
    assert payload.resolution == PersonResolutionStatus.UNKNOWN.value


@pytest.mark.asyncio
async def test_follow_up_refinement(gd_service: GlobalDirectoryService) -> None:
    first = await gd_service.resolve_person("Ramesh")
    assert first.resolution == PersonResolutionStatus.AMBIGUOUS.value
    token = first.refinement_token
    assert token
    refined = await gd_service.refine_resolution(token, organization_hint="Company A")
    assert refined.resolution == PersonResolutionStatus.RESOLVED.value


@pytest.mark.asyncio
async def test_conflicting_role_claims(gd_service: GlobalDirectoryService) -> None:
    payload = await gd_service.resolve_person("Elena Voss")
    assert payload.resolution == PersonResolutionStatus.RESOLVED.value
    assert any(c.get("state") == EvidenceState.CONFLICTING_EVIDENCE.value for c in payload.conflicts)


@pytest.mark.asyncio
async def test_directory_identity_not_authority(gd_service: GlobalDirectoryService) -> None:
    payload = await gd_service.resolve_person("Arun Dev")
    assert payload.entity
    assert "permission" not in str(payload.model_dump()).lower()


@given(
    st.text(
        alphabet=st.characters(whitelist_categories=("L",), whitelist_characters=" -'"),
        min_size=1,
        max_size=40,
    )
)
@settings(max_examples=200, deadline=None)
def test_synthetic_names_do_not_crash(name: str) -> None:
    import asyncio

    async def _run() -> None:
        engine = create_engine(":memory:")
        await engine.init()
        svc = GlobalDirectoryService(GlobalDirectoryRepository(engine))
        cleaned = " ".join(name.split())
        if not cleaned:
            await engine.close()
            return
        payload = await svc.resolve_person(cleaned)
        assert payload.resolution in {
            PersonResolutionStatus.RESOLVED.value,
            PersonResolutionStatus.AMBIGUOUS.value,
            PersonResolutionStatus.UNKNOWN.value,
        }
        await engine.close()

    asyncio.run(_run())
