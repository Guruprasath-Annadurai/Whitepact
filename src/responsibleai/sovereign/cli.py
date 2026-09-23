# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact Sovereign CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import click

from responsibleai.sovereign import cli_core
from responsibleai.sovereign.service import SovereignService


def _emit(data: object, human: str | None, json_mode: bool) -> None:
    cli_core.emit(data, human, json_mode)


@click.group()
def sovereign() -> None:
    """Sovereign governance diagnostics (read/simulate only)."""


@sovereign.command("status")
@click.option("--json", "json_mode", is_flag=True)
def status_cmd(json_mode: bool) -> None:
    cli_core.run_async(cli_core.cmd_status(json_mode))


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
    cli_core.run_async(cli_core.cmd_blast_radius(org, actor, extra_cap, json_mode))


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
    cli_core.run_async(cli_core.cmd_doctor(org, manifest, json_mode))


@sovereign.command("ci")
@click.option("--manifest", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--org", required=True)
@click.option("--json", "json_mode", is_flag=True)
def ci(manifest: Path, org: str, json_mode: bool) -> None:
    cli_core.run_async(cli_core.cmd_ci(manifest, org, json_mode))


@sovereign.command("gauntlet")
@click.option("--org", required=True)
@click.option("--probe", multiple=True)
@click.option("--json", "json_mode", is_flag=True)
def gauntlet_cmd(org: str, probe: tuple[str, ...], json_mode: bool) -> None:
    cli_core.run_async(cli_core.cmd_gauntlet(org, list(probe), json_mode))


@sovereign.command("shadow")
@click.option("--org", required=True)
@click.option("--agent", required=True)
@click.option("--action", required=True)
@click.option("--persist", is_flag=True)
@click.option("--json", "json_mode", is_flag=True)
def shadow_cmd(org: str, agent: str, action: str, persist: bool, json_mode: bool) -> None:
    cli_core.run_async(cli_core.cmd_shadow(org, agent, action, persist, json_mode))


@sovereign.command("xray")
@click.option("--org", required=True)
@click.option("--json", "json_mode", is_flag=True)
def xray_cmd(org: str, json_mode: bool) -> None:
    cli_core.run_async(cli_core.cmd_xray(org, json_mode))


@sovereign.command("sandbox")
@click.option("--json", "json_mode", is_flag=True)
def sandbox_cmd(json_mode: bool) -> None:
    cli_core.run_async(cli_core.cmd_sandbox(json_mode))


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
