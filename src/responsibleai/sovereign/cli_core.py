# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Shared CLI command implementations (single code path for aliases)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import click

from responsibleai.db import create_engine
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.exit_codes import (
    EXIT_GOVERNANCE,
    EXIT_INTERNAL,
    EXIT_INVALID,
    EXIT_OK,
    EXIT_UNAVAILABLE,
    EXIT_UNKNOWN,
)
from responsibleai.sovereign.manifest import load_manifest
from responsibleai.sovereign.redaction import redact_for_debugger
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.sources import SovereignCanonicalStore


def emit(data: object, human: str | None, json_mode: bool) -> None:
    if json_mode:
        click.echo(json.dumps(data, default=str))
    elif human:
        click.echo(human)


def ctx_from(org: str, env: str | None = None) -> SovereignContext:
    return SovereignContext(organization_id=org, environment=env or "development")


async def service() -> SovereignService:
    engine = create_engine(":memory:")
    await engine.init()
    return SovereignService(store=SovereignCanonicalStore.from_engine(engine))


def disposition_exit(payload: dict[str, Any]) -> int:
    disp = payload.get("disposition") or payload.get("status")
    if disp in ("DENY", "denied"):
        return EXIT_GOVERNANCE
    if disp in ("APPROVAL_REQUIRED", "approval_required"):
        return EXIT_UNKNOWN
    if disp in ("UNKNOWN", "unknown"):
        return EXIT_UNKNOWN
    if disp in ("UNAVAILABLE", "unavailable"):
        return EXIT_UNAVAILABLE
    return EXIT_OK


async def cmd_status(json_mode: bool) -> int:
    st = SovereignService().get_status()
    emit(st.model_dump(), f"Sovereign {st.sovereign_version}", json_mode)
    return EXIT_OK


async def cmd_xray(org: str, json_mode: bool) -> int:
    svc = await service()
    result = await svc.build_xray_async(ctx_from(org))
    emit(redact_for_debugger(result.model_dump()), None, json_mode)
    return EXIT_OK


async def cmd_trace(org: str, evidence_id: str, json_mode: bool) -> int:
    svc = await service()
    trace = await svc.trace_evidence_async(ctx_from(org), evidence_id)
    emit(trace.model_dump(), None, json_mode)
    return EXIT_OK


async def cmd_explain(org: str, evidence_id: str | None, identity_id: str | None, json_mode: bool) -> int:
    svc = await service()
    ctx = ctx_from(org)
    if evidence_id:
        out = await svc.explain_evidence_async(ctx, evidence_id)
    elif identity_id:
        out = await svc.explain_identity_async(ctx, identity_id)
    else:
        emit({"error": "evidence_id or identity_id required"}, None, json_mode)
        return EXIT_INVALID
    emit(out.model_dump(), None, json_mode)
    return disposition_exit(out.model_dump())


async def cmd_gauntlet(org: str, probes: list[str], json_mode: bool) -> int:
    svc = await service()
    report = await svc.run_gauntlet_async(ctx_from(org), probe_ids=probes or None)
    payload = report.model_dump()
    emit(payload, None, json_mode)
    if any(c.get("status") == "FAIL" for c in payload.get("cases", [])):
        return EXIT_GOVERNANCE
    return EXIT_OK


async def cmd_ci(manifest: Path, org: str, json_mode: bool) -> int:
    svc = await service()
    m = load_manifest(manifest)
    ctx = ctx_from(org)
    drift = await svc.detect_drift_async(ctx, m)
    gauntlet = await svc.run_gauntlet_async(
        ctx, probe_ids=["tenant_guard", "matrix_simulation_no_consequential_counter"]
    )
    report = {
        "manifest_valid": True,
        "drift_facts": len(drift.facts),
        "gauntlet_cases": len(gauntlet.cases),
        "gauntlet_failures": sum(1 for c in gauntlet.cases if c.status.value == "FAIL"),
        "production_opened": False,
        "labels": ["GOVERNANCE_CI", "ZERO_EFFECT"],
    }
    emit(report, None, json_mode)
    if report["gauntlet_failures"]:
        return EXIT_GOVERNANCE
    return EXIT_OK if report["drift_facts"] == 0 else EXIT_GOVERNANCE


def run_async(coro) -> None:
    try:
        code = asyncio.run(coro)
        sys.exit(code)
    except click.ClickException:
        raise
    except Exception as exc:  # noqa: BLE001
        emit({"error": str(exc), "disposition": "INTERNAL_ERROR"}, str(exc), False)
        sys.exit(EXIT_INTERNAL)
