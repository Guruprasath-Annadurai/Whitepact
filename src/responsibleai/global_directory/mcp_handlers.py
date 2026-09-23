# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

import mcp.types as types

import responsibleai.dashboard.app as dashboard_app
from responsibleai.global_directory.repository import GlobalDirectoryRepository
from responsibleai.global_directory.service import GlobalDirectoryService

_READ_ONLY = types.ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=True, destructiveHint=False
)

GLOBAL_DIRECTORY_TOOL_DEFS: list[types.Tool] = [
    types.Tool(
        name="global_directory.resolve_entity",
        title="Resolve global directory entity",
        annotations=_READ_ONLY,
        description="Resolve a public/professional entity query to a canonical directory entity or ambiguity set.",
        inputSchema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    ),
    types.Tool(
        name="global_directory.search_entities",
        title="Search global directory",
        annotations=_READ_ONLY,
        description="Search the global entity graph for candidate matches.",
        inputSchema={
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 10}},
            "required": ["query"],
        },
    ),
    types.Tool(
        name="global_directory.get_entity",
        title="Get global directory entity",
        annotations=_READ_ONLY,
        description="Fetch machine-readable entity profile with claims and provenance.",
        inputSchema={"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]},
    ),
    types.Tool(
        name="global_directory.get_relationships",
        title="Get entity relationships",
        annotations=_READ_ONLY,
        description="List evidence-backed relationships for an entity.",
        inputSchema={"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]},
    ),
    types.Tool(
        name="global_directory.get_entity_evidence",
        title="Get entity evidence bundle",
        annotations=_READ_ONLY,
        description="Return claims, sources, and evidence states for an entity.",
        inputSchema={"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]},
    ),
    types.Tool(
        name="global_directory.verify_claim",
        title="Verify directory claim",
        annotations=_READ_ONLY,
        description="Re-check a claim's evidence state (read-only; does not grant authority).",
        inputSchema={"type": "object", "properties": {"claim_id": {"type": "string"}}, "required": ["claim_id"]},
    ),
    types.Tool(
        name="global_directory.get_trust_context",
        title="Get directory trust context",
        annotations=_READ_ONLY,
        description="Structured trust signals for governance risk (not execution authority).",
        inputSchema={"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]},
    ),
    types.Tool(
        name="global_directory.check_identity_conflict",
        title="Check identity conflict / ambiguity",
        annotations=_READ_ONLY,
        description="Detect ambiguous or conflicting identity resolution for a query.",
        inputSchema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    ),
    types.Tool(
        name="global_directory.resolve_person",
        title="Resolve person (evidence-driven)",
        annotations=_READ_ONLY,
        description="Universal person resolution returning RESOLVED, AMBIGUOUS, or UNKNOWN with grounded evidence.",
        inputSchema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    ),
    types.Tool(
        name="global_directory.refine_resolution",
        title="Refine ambiguous person resolution",
        annotations=_READ_ONLY,
        description="Refine a prior ambiguous person lookup using organization/profession hints.",
        inputSchema={
            "type": "object",
            "properties": {
                "refinement_token": {"type": "string"},
                "organization_hint": {"type": "string"},
                "profession_hint": {"type": "string"},
            },
            "required": ["refinement_token"],
        },
    ),
]


async def _svc() -> GlobalDirectoryService:
    if dashboard_app._db_engine is None:
        raise RuntimeError("Database not initialized")
    return GlobalDirectoryService(GlobalDirectoryRepository(dashboard_app._db_engine))


async def _handle_resolve_entity(args: dict[str, Any]) -> dict[str, Any]:
    svc = await _svc()
    result = await svc.resolve_entity(str(args["query"]))
    return result.model_dump()


async def _handle_search_entities(args: dict[str, Any]) -> dict[str, Any]:
    svc = await _svc()
    limit = int(args.get("limit", 10))
    candidates = await svc.search_entities(str(args["query"]), limit=limit)
    return {"candidates": [c.model_dump() for c in candidates]}


async def _handle_get_entity(args: dict[str, Any]) -> dict[str, Any]:
    svc = await _svc()
    payload = await svc.get_machine_response(str(args["entity_id"]))
    return payload.model_dump()


async def _handle_get_relationships(args: dict[str, Any]) -> dict[str, Any]:
    svc = await _svc()
    rels = await svc._repo.list_relationships(str(args["entity_id"]))  # noqa: SLF001
    return {"relationships": [r.model_dump() for r in rels]}


async def _handle_get_entity_evidence(args: dict[str, Any]) -> dict[str, Any]:
    return await _handle_get_entity(args)


async def _handle_verify_claim(args: dict[str, Any]) -> dict[str, Any]:
    svc = await _svc()
    return await svc.verify_claim(str(args["claim_id"]))


async def _handle_get_trust_context(args: dict[str, Any]) -> dict[str, Any]:
    svc = await _svc()
    payload = await svc.get_machine_response(str(args["entity_id"]))
    from responsibleai.global_directory.governance_bridge import build_governance_context

    gov = build_governance_context(payload.entity, payload.claims)
    return {
        "trust_context": gov.trust_context.model_dump(),
        "recommended_posture": gov.recommended_posture,
        "authority_note": gov.authority_note,
    }


async def _handle_check_identity_conflict(args: dict[str, Any]) -> dict[str, Any]:
    svc = await _svc()
    return await svc.check_identity_conflict(str(args["query"]))


async def _handle_resolve_person(args: dict[str, Any]) -> dict[str, Any]:
    svc = await _svc()
    payload = await svc.resolve_person(str(args["query"]))
    return payload.model_dump()


async def _handle_refine_resolution(args: dict[str, Any]) -> dict[str, Any]:
    svc = await _svc()
    payload = await svc.refine_resolution(
        str(args["refinement_token"]),
        organization_hint=args.get("organization_hint"),
        profession_hint=args.get("profession_hint"),
    )
    return payload.model_dump()


GLOBAL_DIRECTORY_HANDLERS: dict[str, Any] = {
    "global_directory.resolve_entity": _handle_resolve_entity,
    "global_directory.search_entities": _handle_search_entities,
    "global_directory.get_entity": _handle_get_entity,
    "global_directory.get_relationships": _handle_get_relationships,
    "global_directory.get_entity_evidence": _handle_get_entity_evidence,
    "global_directory.verify_claim": _handle_verify_claim,
    "global_directory.get_trust_context": _handle_get_trust_context,
    "global_directory.check_identity_conflict": _handle_check_identity_conflict,
    "global_directory.resolve_person": _handle_resolve_person,
    "global_directory.refine_resolution": _handle_refine_resolution,
}
