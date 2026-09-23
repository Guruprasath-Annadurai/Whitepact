# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.global_directory.enums import DataScope, EvidenceState
from responsibleai.global_directory.governance_bridge import build_governance_context
from responsibleai.global_directory.identifiers import extract_identifiers, normalize_free_text
from responsibleai.global_directory.repository import GlobalDirectoryRepository
from responsibleai.global_directory.service import GlobalDirectoryService
from responsibleai.mcp.tools import PRODUCTION_TOOL_DEFS
from responsibleai.net.egress import EgressSecurityError, validate_outbound_url, DestinationPolicy


@pytest.fixture
async def gd_service():
    engine = create_engine(":memory:")
    await engine.init()
    svc = GlobalDirectoryService(GlobalDirectoryRepository(engine))
    yield svc
    await engine.close()


@pytest.mark.asyncio
async def test_resolve_person_via_fixture_catalog(gd_service: GlobalDirectoryService) -> None:
    result = await gd_service.resolve_entity("Guruprasath Annadurai")
    assert result.status == "resolved"
    assert result.entity is not None
    assert result.entity.entity_type.value == "PERSON"
    assert result.entity.confidence > 0.8
    payload = await gd_service.get_machine_response(result.entity.entity_id)
    assert payload.summary
    assert any(c.predicate == "ASSOCIATED_WITH" for c in payload.claims)


@pytest.mark.asyncio
async def test_same_name_disambiguation(gd_service: GlobalDirectoryService) -> None:
    result = await gd_service.resolve_entity("Alex Smith")
    assert result.status == "ambiguous"
    assert len(result.candidates) >= 2


@pytest.mark.asyncio
async def test_github_repository_identifier_resolution(gd_service: GlobalDirectoryService) -> None:
    result = await gd_service.resolve_entity("github.com/Guruprasath-Annadurai/Whitepact")
    assert result.status == "resolved"
    assert result.entity is not None
    assert result.entity.entity_type.value in {"PROJECT", "REPOSITORY"}


def test_identifier_extraction_github() -> None:
    ids = extract_identifiers("https://github.com/Guruprasath-Annadurai/Whitepact")
    assert ids[0].identifier_type == "github_repository"


@pytest.mark.asyncio
async def test_governance_bridge_does_not_imply_authority(gd_service: GlobalDirectoryService) -> None:
    result = await gd_service.resolve_entity("WhitePact")
    assert result.entity
    payload = await gd_service.get_machine_response(result.entity.entity_id)
    gov = build_governance_context(payload.entity, payload.claims)
    assert "does not mint execution authority" in gov.authority_note
    assert gov.recommended_posture in {"LOW", "MEDIUM", "HIGH", "UNKNOWN_ENTITY"}


def test_global_directory_mcp_tools_read_only() -> None:
    names = {t.name for t in PRODUCTION_TOOL_DEFS if t.name.startswith("global_directory.")}
    assert len(names) == 8
    for tool in PRODUCTION_TOOL_DEFS:
        if tool.name.startswith("global_directory."):
            assert tool.annotations is not None
            assert tool.annotations.readOnlyHint is True


def test_ssrf_blocks_localhost_discovery_url() -> None:
    with pytest.raises(EgressSecurityError):
        validate_outbound_url("http://127.0.0.1/evil", DestinationPolicy.PUBLIC_ONLY)


def test_normalize_free_text_casefold() -> None:
    assert normalize_free_text("  Guruprasath   Annadurai ") == "guruprasath annadurai"


@pytest.mark.asyncio
async def test_global_scope_only_on_persisted_entity(gd_service: GlobalDirectoryService) -> None:
    result = await gd_service.resolve_entity("Guruprasath Annadurai")
    assert result.entity
    repo = gd_service._repo
    async with repo._engine.raw.connect() as conn:  # noqa: SLF001
        from sqlalchemy import select
        from responsibleai.db.engine import global_directory_entities

        row = (
            await conn.execute(
                select(global_directory_entities).where(
                    global_directory_entities.c.entity_id == result.entity.entity_id
                )
            )
        ).first()
        assert row.data_scope == DataScope.GLOBAL_PUBLIC_EVIDENCE.value
