# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact Sovereign CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import click

from responsibleai.sovereign import cli_core
from responsibleai.sovereign.exit_codes import EXIT_INVALID
from responsibleai.sovereign.service import SovereignService


def _emit(data: object, human: str | None, json_mode: bool) -> None:
    cli_core.emit(data, human, json_mode)


@click.group()
def sovereign() -> None:
    """Sovereign governance diagnostics (read/simulate only)."""


@sovereign.command("status")
@click.option("--json", "json_mode", is_flag=True)
def status_cmd(json_mode: bool) -> None:
    cli_core.run_async(cli_core.cmd_status(json_mode), json_mode=json_mode)


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
    cli_core.run_async(
        cli_core.cmd_blast_radius(org, actor, extra_cap, json_mode), json_mode=json_mode
    )


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
@click.option("--remote", is_flag=True, help="Probe saved base URL. Does not send credentials.")
@click.option("--json", "json_mode", is_flag=True)
def doctor(org: str | None, manifest: Path | None, remote: bool, json_mode: bool) -> None:
    cli_core.run_async(
        cli_core.cmd_doctor(org, manifest, json_mode, remote=remote),
        json_mode=json_mode,
    )


@sovereign.command("ci")
@click.option("--manifest", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--org", required=True)
@click.option("--json", "json_mode", is_flag=True)
def ci(manifest: Path, org: str, json_mode: bool) -> None:
    cli_core.run_async(cli_core.cmd_ci(manifest, org, json_mode), json_mode=json_mode)


@sovereign.command("gauntlet")
@click.option("--org", required=True)
@click.option("--probe", multiple=True)
@click.option("--json", "json_mode", is_flag=True)
def gauntlet_cmd(org: str, probe: tuple[str, ...], json_mode: bool) -> None:
    cli_core.run_async(cli_core.cmd_gauntlet(org, list(probe), json_mode), json_mode=json_mode)


@sovereign.command("shadow")
@click.option("--org", required=True)
@click.option("--agent", required=True)
@click.option("--action", required=True)
@click.option("--persist", is_flag=True)
@click.option("--json", "json_mode", is_flag=True)
def shadow_cmd(org: str, agent: str, action: str, persist: bool, json_mode: bool) -> None:
    cli_core.run_async(
        cli_core.cmd_shadow(org, agent, action, persist, json_mode), json_mode=json_mode
    )


@sovereign.command("xray")
@click.option("--org", required=True)
@click.option("--json", "json_mode", is_flag=True)
def xray_cmd(org: str, json_mode: bool) -> None:
    cli_core.run_async(cli_core.cmd_xray(org, json_mode), json_mode=json_mode)


@sovereign.command("sandbox")
@click.option("--json", "json_mode", is_flag=True)
def sandbox_cmd(json_mode: bool) -> None:
    cli_core.run_async(cli_core.cmd_sandbox(json_mode), json_mode=json_mode)


def register_top_level(main: click.Group) -> None:
    @main.command("init")
    @click.option("--path", type=click.Path(path_type=Path), default=Path("."))
    def init_cmd(path: Path) -> None:
        from responsibleai.sovereign.devconfig import init_scaffolding

        manifest = init_scaffolding(path)
        click.echo(f"Created scaffold {manifest} (no production authority)")

    @main.command("connect")
    @click.option("--url", default="http://127.0.0.1:8000")
    @click.option("--org", help="Local label only. Hosted calls use the server tenant.")
    def connect_cmd(url: str, org: str | None) -> None:
        from responsibleai.sovereign.devconfig import SovereignConnection, save_connection
        from responsibleai.sovereign.reachability import probe_base_url, validate_developer_base_url

        try:
            base_url = validate_developer_base_url(url)
        except ValueError as exc:
            click.echo(str(exc), err=True)
            raise click.exceptions.Exit(EXIT_INVALID) from exc
        probe = probe_base_url(base_url)
        state = "verified" if probe.ok else "unverified"
        save_connection(
            SovereignConnection(
                base_url=base_url,
                organization_id=org,
                verification_state=state,
                verification_detail=probe.message,
            )
        )
        banner = "VERIFIED CONNECTION" if probe.ok else "SAVED UNVERIFIED CONTEXT"
        click.echo(banner)
        click.echo(probe.message)
        click.echo("No credentials were stored. A saved context is not authorization.")
        if org:
            click.echo(
                "organization_id is a local label. Hosted calls use the authenticated server tenant."
            )

    @main.group("context")
    def context_group() -> None:
        pass

    @context_group.command("list")
    def context_list() -> None:
        from responsibleai.sovereign.devconfig import load_connection

        conn = load_connection()
        label = (
            "VERIFIED CONNECTION"
            if conn.verification_state == "verified"
            else "SAVED UNVERIFIED CONTEXT"
        )
        click.echo(label)
        click.echo(json.dumps(conn.__dict__, sort_keys=True))

    @context_group.command("current")
    def context_current() -> None:
        from responsibleai.sovereign.devconfig import load_connection

        conn = load_connection()
        label = (
            "VERIFIED CONNECTION"
            if conn.verification_state == "verified"
            else "SAVED UNVERIFIED CONTEXT"
        )
        click.echo(label)
        click.echo(json.dumps(conn.__dict__, sort_keys=True))

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
