# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from responsibleai.global_directory.deps import get_global_directory_service
from responsibleai.global_directory.models import MachineDirectoryResponse, ResolutionResult
from responsibleai.global_directory.repository import GlobalDirectoryRepository
from responsibleai.global_directory.service import GlobalDirectoryService

router = APIRouter(prefix="/api/v1/global-directory", tags=["global-directory"])


@router.get("/resolve", response_model=ResolutionResult)
async def resolve_entity(
    q: str = Query(..., min_length=1, max_length=512),
    service: GlobalDirectoryService = Depends(get_global_directory_service),
) -> ResolutionResult:
    return await service.resolve_entity(q)


@router.get("/search")
async def search_entities(
    q: str = Query(..., min_length=1, max_length=512),
    limit: int = Query(10, ge=1, le=50),
    service: GlobalDirectoryService = Depends(get_global_directory_service),
) -> dict[str, object]:
    candidates = await service.search_entities(q, limit=limit)
    return {
        "query": q,
        "candidates": [c.model_dump() for c in candidates],
    }


@router.get("/entities/{entity_id}", response_model=MachineDirectoryResponse)
async def get_entity(
    entity_id: str,
    service: GlobalDirectoryService = Depends(get_global_directory_service),
) -> MachineDirectoryResponse:
    payload = await service.get_machine_response(entity_id)
    if payload.entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return payload


@router.get("/entities/{entity_id}/relationships")
async def get_relationships(
    entity_id: str,
    service: GlobalDirectoryService = Depends(get_global_directory_service),
) -> dict[str, object]:
    rels = await service._repo.list_relationships(entity_id)  # noqa: SLF001
    return {"entity_id": entity_id, "relationships": [r.model_dump() for r in rels]}


@router.get("/entities/{entity_id}/evidence", response_model=MachineDirectoryResponse)
async def get_entity_evidence(
    entity_id: str,
    service: GlobalDirectoryService = Depends(get_global_directory_service),
) -> MachineDirectoryResponse:
    return await service.get_machine_response(entity_id)


@router.get("/entities/{entity_id}/trust-context")
async def get_trust_context(
    entity_id: str,
    service: GlobalDirectoryService = Depends(get_global_directory_service),
) -> dict[str, object]:
    payload = await service.get_machine_response(entity_id)
    if payload.entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    from responsibleai.global_directory.governance_bridge import build_governance_context

    claims = payload.claims
    gov = build_governance_context(payload.entity, claims)
    return {
        "entity_id": entity_id,
        "trust_context": gov.trust_context.model_dump(),
        "recommended_posture": gov.recommended_posture,
        "authority_note": gov.authority_note,
    }
