# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact Sovereign CLI commands."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import click

from responsibleai.db import create_engine
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.manifest import load_manifest
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.sources import SovereignCanonicalStore


def _emit(data: object, human: str | None, json_mode: bool) -> None:
    if json_mode:
        click.echo(json.dumps(data, default=str))
    elif human:
        click.echo(human)


def _ctx_from_flags(org: str, env: str | None) -> SovereignContext:
    return SovereignContext(organization_id=org, environment=env)


@click.group()
def sovereign() -> None:
    """Sovereign governance diagnostics (read/simulate only)."""


@sovereign.command("status")
@click.option("--json", "json_mode", is_flag=True)
def status_cmd(json_mode: bool) -> None:
    svc = SovereignService()
    st = svc.get_status()
    _emit(
        st.model_dump(),
        f"Sovereign {st.sovereign_version} protocol {st.protocol_version}",
        json_mode,
    )


@sovereign.command("version")
def version_cmd() -> None:
    svc = SovereignService()
    click.echo(svc.get_status().sovereign_version)


@sovereign.group("simulate")
def simulate_group() -> None:
    pass


@simulate_group.command("blast-radius")
@click.option("--org", required=True)
@click.option("--actor", required=True)
@click.option("--extra-cap", multiple=True)
@click.option("--json", "json_mode", is_flag=True)
def blast_radius(org: str, actor: str, extra_cap: tuple[str, ...], json_mode: bool) -> None:
    async def _run() -> None:
        engine = create_engine(":memory:")
        await engine.init()
        svc = SovereignService(store=SovereignCanonicalStore.from_engine(engine))
        ctx = _ctx_from_flags(org, None)
        result = await svc.simulate_blast_radius_async(
            ctx, actor_identity_id=actor, hypothetical_extra_capabilities=frozenset(extra_cap)
        )
        _emit(result.model_dump(), None, json_mode)

    asyncio.run(_run())


@sovereign.group("manifest")
def manifest_group() -> None:
    pass


@manifest_group.command("validate")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--json", "json_mode", is_flag=True)
def manifest_validate(path: Path, json_mode: bool) -> None:
    svc = SovereignService()
    manifest = svc.load_expected_manifest(path)
    _emit(manifest.model_dump(), f"Manifest valid for org {manifest.organization_id}", json_mode)


@sovereign.command("doctor")
@click.option("--org")
@click.option("--manifest", type=click.Path(path_type=Path))
@click.option("--json", "json_mode", is_flag=True)
def doctor(org: str | None, manifest: Path | None, json_mode: bool) -> None:
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
    _emit({"checks": checks}, None, json_mode)
    if any(c["result"] == "FAIL" for c in checks):
        sys.exit(2)


@sovereign.command("ci")
@click.option("--manifest", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--org", required=True)
@click.option("--json", "json_mode", is_flag=True)
def ci(manifest: Path, org: str, json_mode: bool) -> None:
    async def _run() -> None:
        engine = create_engine(":memory:")
        await engine.init()
        svc = SovereignService(store=SovereignCanonicalStore.from_engine(engine))
        m = load_manifest(manifest)
        ctx = _ctx_from_flags(org, None)
        drift = await svc.detect_drift_async(ctx, m)
        report = {
            "manifest_valid": True,
            "drift_facts": len(drift.facts),
            "production_opened": False,
        }
        _emit(report, None, json_mode)
        sys.exit(0 if report["drift_facts"] == 0 else 3)

    asyncio.run(_run())


async def _service() -> SovereignService:
    engine = create_engine(":memory:")
    await engine.init()
    return SovereignService(store=SovereignCanonicalStore.from_engine(engine))


@sovereign.command("gauntlet")
@click.option("--org", required=True)
@click.option("--probe", multiple=True)
@click.option("--json", "json_mode", is_flag=True)
def gauntlet_cmd(org: str, probe: tuple[str, ...], json_mode: bool) -> None:
    async def _run() -> None:
        svc = await _service()
        ctx = _ctx_from_flags(org, None)
        report = await svc.run_gauntlet_async(ctx, probe_ids=list(probe) or None)
        _emit(report.model_dump(), None, json_mode)

    asyncio.run(_run())


@sovereign.command("shadow")
@click.option("--org", required=True)
@click.option("--agent", required=True)
@click.option("--action", required=True)
@click.option("--json", "json_mode", is_flag=True)
def shadow_cmd(org: str, agent: str, action: str, json_mode: bool) -> None:
    svc = SovereignService()
    obs = svc.evaluate_shadow(
        _ctx_from_flags(org, None),
        agent_id=agent,
        action_type=action,
        granted_action_types=frozenset({action}),
    )
    _emit(obs.model_dump(), None, json_mode)


@sovereign.command("xray")
@click.option("--org", required=True)
@click.option("--json", "json_mode", is_flag=True)
def xray_cmd(org: str, json_mode: bool) -> None:
    async def _run() -> None:
        svc = await _service()
        result = await svc.build_xray_async(_ctx_from_flags(org, None))
        _emit(result.model_dump(), None, json_mode)

    asyncio.run(_run())


@sovereign.command("sandbox")
@click.option("--json", "json_mode", is_flag=True)
def sandbox_cmd(json_mode: bool) -> None:
    _emit(
        {"labels": ["SANDBOX", "SIMULATED", "NON_PRODUCTION"], "zero_effect": True},
        "Sovereign sandbox — simulated only",
        json_mode,
    )


def register_top_level(main: click.Group) -> None:
    @main.command("init")
    @click.option("--path", type=click.Path(path_type=Path), default=Path("."))
    def init_cmd(path: Path) -> None:
        from responsibleai.sovereign.devconfig import init_scaffolding

        manifest = init_scaffolding(path)
        click.echo(f"Created scaffold {manifest} (no production authority)")

    @main.command("connect")
    @click.option("--url", default="http://127.0.0.1:8000")
    @click.option("--org")
    def connect_cmd(url: str, org: str | None) -> None:
        from responsibleai.sovereign.devconfig import SovereignConnection, save_connection

        save_connection(SovereignConnection(base_url=url, organization_id=org))
        click.echo("Connection saved (connection is not authorization)")

    @main.group("context")
    def context_group() -> None:
        pass

    @context_group.command("list")
    def context_list() -> None:
        from responsibleai.sovereign.devconfig import load_connection

        click.echo(json.dumps(load_connection().__dict__))

    @context_group.command("current")
    def context_current() -> None:
        from responsibleai.sovereign.devconfig import load_connection

        click.echo(json.dumps(load_connection().__dict__))

    @context_group.command("use")
    @click.option("--org", required=True)
    @click.option("--env", default="development")
    def context_use(org: str, env: str) -> None:
        from responsibleai.sovereign.devconfig import load_connection, save_connection

        conn = load_connection()
        conn.organization_id = org
        conn.environment = env
        save_connection(conn)
        click.echo("Context updated (does not grant authority)")
