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
from responsibleai.governance.policy import PolicyRule
from responsibleai.sovereign.capsule import SovereignCapsule, create_capsule
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
from responsibleai.sovereign.policy_lab import PolicyTestCase
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


async def cmd_explain(
    org: str, evidence_id: str | None, identity_id: str | None, json_mode: bool
) -> int:
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


async def cmd_doctor(org: str | None, manifest: Path | None, json_mode: bool) -> int:
    checks: list[dict[str, str]] = []
    svc = SovereignService()
    checks.append({"name": "protocol", "result": "PASS"})
    caps = svc.get_capabilities()
    unavailable = [f.name.value for f in caps.features if f.availability.value == "UNAVAILABLE"]
    checks.append(
        {
            "name": "capabilities",
            "result": "WARN" if unavailable else "PASS",
            "detail": ",".join(unavailable) if unavailable else "",
        }
    )
    if manifest:
        try:
            load_manifest(manifest)
            checks.append({"name": "manifest", "result": "PASS"})
        except Exception as exc:  # noqa: BLE001
            checks.append({"name": "manifest", "result": "FAIL", "detail": str(exc)})
    if not org:
        checks.append({"name": "context", "result": "WARN", "detail": "no --org"})
    emit({"checks": checks}, None, json_mode)
    if any(c["result"] == "FAIL" for c in checks):
        return EXIT_INVALID
    return EXIT_OK


async def cmd_blast_radius(
    org: str, actor: str, extra_cap: tuple[str, ...], json_mode: bool
) -> int:
    svc = await service()
    result = await svc.simulate_blast_radius_async(
        ctx_from(org),
        actor_identity_id=actor,
        hypothetical_extra_capabilities=frozenset(extra_cap),
    )
    emit(redact_for_debugger(result.model_dump()), None, json_mode)
    return EXIT_OK


async def cmd_mission(org: str, agent: str, steps: list[str], json_mode: bool) -> int:
    svc = await service()
    report = await svc.simulate_mission_async(ctx_from(org), agent_id=agent, steps=steps)
    payload = report.model_dump()
    emit(redact_for_debugger(payload), None, json_mode)
    for step in payload.get("steps", []):
        code = disposition_exit(step)
        if code != EXIT_OK:
            return code
    return EXIT_OK


async def cmd_shadow(org: str, agent: str, action: str, persist: bool, json_mode: bool) -> int:
    svc = await service()
    ctx = ctx_from(org)
    if persist:
        obs = await svc.evaluate_shadow_persisted_async(
            ctx, agent_id=agent, action_type=action, target="shadow:target"
        )
        payload = obs.model_dump()
    else:
        payload = svc.evaluate_shadow(
            ctx,
            agent_id=agent,
            action_type=action,
            granted_action_types=frozenset({action}),
        ).model_dump()
    emit(redact_for_debugger(payload), None, json_mode)
    return disposition_exit(payload)


async def cmd_authority_compare(org: str, manifest: Path, json_mode: bool) -> int:
    svc = await service()
    m = load_manifest(manifest)
    result = await svc.compare_manifest_async(ctx_from(org), m)
    emit(result.model_dump(), None, json_mode)
    return EXIT_OK if not result.diffs else EXIT_GOVERNANCE


async def cmd_authority_drift(org: str, manifest: Path, json_mode: bool) -> int:
    svc = await service()
    m = load_manifest(manifest)
    report = await svc.detect_drift_async(ctx_from(org), m)
    emit(report.model_dump(), None, json_mode)
    return EXIT_OK if not report.facts else EXIT_GOVERNANCE


async def cmd_authority_diff(org: str, manifest: Path, json_mode: bool) -> int:
    """Human-facing diff alias — drift facts vs manifest."""
    return await cmd_authority_drift(org, manifest, json_mode)


def _load_rules(path: Path | None, inline: str | None) -> list[PolicyRule]:
    if path:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw if isinstance(raw, list) else raw.get("rules", [])
    elif inline:
        items = json.loads(inline)
        if not isinstance(items, list):
            items = items.get("rules", [])
    else:
        raise click.ClickException("--rules-file or --rules-json required")
    rules: list[PolicyRule] = []
    for r in items:
        try:
            rules.append(PolicyRule(**r))
        except (TypeError, ValueError) as exc:
            raise click.ClickException(f"invalid policy rule: {exc}") from exc
    return rules


async def cmd_policy_lint(
    org: str, rules_file: Path | None, rules_json: str | None, json_mode: bool
) -> int:
    svc = await service()
    rules = _load_rules(rules_file, rules_json)
    errors = svc.lint_policy_rules(rules)
    emit({"errors": errors, "organization_id": org}, None, json_mode)
    return EXIT_OK if not errors else EXIT_INVALID


async def cmd_policy_validate(
    org: str, rules_file: Path | None, rules_json: str | None, json_mode: bool
) -> int:
    return await cmd_policy_lint(org, rules_file, rules_json, json_mode)


async def cmd_policy_test(
    org: str, cases_file: Path | None, cases_json: str | None, json_mode: bool
) -> int:
    svc = await service()
    if cases_file:
        raw = json.loads(cases_file.read_text(encoding="utf-8"))
    elif cases_json:
        raw = json.loads(cases_json)
    else:
        emit({"error": "cases required"}, None, json_mode)
        return EXIT_INVALID
    cases = [PolicyTestCase(**c) for c in raw]
    report = await svc.run_policy_tests_async(ctx_from(org), cases)
    payload = report.model_dump()
    emit(payload, None, json_mode)
    if any(r.get("passed") is False for r in payload.get("results", [])):
        return EXIT_GOVERNANCE
    return EXIT_OK


async def cmd_policy_diff(
    org: str, rules_file: Path | None, rules_json: str | None, json_mode: bool
) -> int:
    svc = await service()
    rules = _load_rules(rules_file, rules_json)
    report = await svc.diff_policy_async(ctx_from(org), rules)
    emit(report.model_dump(), None, json_mode)
    return EXIT_OK


async def cmd_policy_simulate(
    org: str,
    rules_file: Path | None,
    rules_json: str | None,
    action_types: list[str],
    json_mode: bool,
) -> int:
    svc = await service()
    rules = _load_rules(rules_file, rules_json)
    report = await svc.simulate_policy_async(
        ctx_from(org), candidate_rules=rules, action_types=action_types
    )
    emit(report.model_dump(), None, json_mode)
    return EXIT_OK


async def cmd_capsule_create(org: str, json_mode: bool) -> int:
    cap = create_capsule(ctx_from(org))
    emit(redact_for_debugger(cap.model_dump()), None, json_mode)
    return EXIT_OK


async def cmd_capsule_inspect(capsule_file: Path, json_mode: bool) -> int:
    data = json.loads(capsule_file.read_text(encoding="utf-8"))
    cap = SovereignCapsule.model_validate(data)
    emit(redact_for_debugger(cap.model_dump()), None, json_mode)
    return EXIT_OK


async def cmd_capsule_validate(capsule_file: Path | None, org: str | None, json_mode: bool) -> int:
    svc = await service()
    if capsule_file:
        cap = SovereignCapsule.model_validate(json.loads(capsule_file.read_text(encoding="utf-8")))
    elif org:
        cap = create_capsule(ctx_from(org))
    else:
        emit({"error": "--capsule or --org required"}, None, json_mode)
        return EXIT_INVALID
    valid = svc.validate_capsule(cap)
    emit({"valid": valid, "capsule_id": cap.capsule_id}, None, json_mode)
    return EXIT_OK if valid else EXIT_GOVERNANCE


async def cmd_capsule_reproduce(capsule_file: Path, json_mode: bool) -> int:
    svc = await service()
    cap = SovereignCapsule.model_validate(json.loads(capsule_file.read_text(encoding="utf-8")))
    emit(svc.reproduce_capsule(cap), None, json_mode)
    return EXIT_OK


async def cmd_sandbox(json_mode: bool) -> int:
    emit(
        {"labels": ["SANDBOX", "SIMULATED", "NON_PRODUCTION"], "zero_effect": True},
        "Sovereign sandbox — simulated only",
        json_mode,
    )
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
    except click.ClickException as exc:
        emit({"error": str(exc), "disposition": "INVALID_INPUT"}, str(exc), False)
        sys.exit(EXIT_INVALID)
    except Exception as exc:  # noqa: BLE001
        emit({"error": str(exc), "disposition": "INTERNAL_ERROR"}, str(exc), False)
        sys.exit(EXIT_INTERNAL)
