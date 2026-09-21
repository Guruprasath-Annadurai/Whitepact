# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Top-level whitepact command aliases → shared cli_core implementations."""

from __future__ import annotations

from pathlib import Path

import click

from responsibleai.sovereign import cli_core
from responsibleai.sovereign.exit_codes import EXIT_UNAVAILABLE
from responsibleai.sovereign.redaction import redact_for_debugger


def register_top_level_aliases(main: click.Group) -> None:
    @main.command("doctor")
    @click.option("--org")
    @click.option("--manifest", type=click.Path(path_type=Path))
    @click.option("--json", "json_mode", is_flag=True)
    def doctor_top(org: str | None, manifest: Path | None, json_mode: bool) -> None:
        from responsibleai.sovereign.cli import doctor as sovereign_doctor

        ctx = click.get_current_context()
        ctx.invoke(sovereign_doctor, org=org, manifest=manifest, json_mode=json_mode)

    @main.command("ci")
    @click.option("--manifest", type=click.Path(exists=True, path_type=Path), required=True)
    @click.option("--org", required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def ci_top(manifest: Path, org: str, json_mode: bool) -> None:
        cli_core.run_async(cli_core.cmd_ci(manifest, org, json_mode))

    @main.command("xray")
    @click.option("--org", required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def xray_top(org: str, json_mode: bool) -> None:
        cli_core.run_async(cli_core.cmd_xray(org, json_mode))

    @main.command("trace")
    @click.option("--org", required=True)
    @click.option("--evidence", required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def trace_top(org: str, evidence: str, json_mode: bool) -> None:
        cli_core.run_async(cli_core.cmd_trace(org, evidence, json_mode))

    @main.command("explain")
    @click.option("--org", required=True)
    @click.option("--evidence")
    @click.option("--identity")
    @click.option("--json", "json_mode", is_flag=True)
    def explain_top(org: str, evidence: str | None, identity: str | None, json_mode: bool) -> None:
        cli_core.run_async(cli_core.cmd_explain(org, evidence, identity, json_mode))

    @main.group("authority")
    def authority_group() -> None:
        pass

    @authority_group.command("drift")
    @click.option("--org", required=True)
    @click.option("--manifest", type=click.Path(exists=True, path_type=Path), required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def authority_drift(org: str, manifest: Path, json_mode: bool) -> None:
        from responsibleai.sovereign.exit_codes import EXIT_GOVERNANCE, EXIT_OK
        from responsibleai.sovereign.manifest import load_manifest

        async def _run() -> int:
            svc = await cli_core.service()
            report = await svc.detect_drift_async(cli_core.ctx_from(org), load_manifest(manifest))
            cli_core.emit(report.model_dump(), None, json_mode)
            return EXIT_OK if not report.facts else EXIT_GOVERNANCE

        cli_core.run_async(_run())

    @main.group("simulate")
    def simulate_top() -> None:
        pass

    @simulate_top.command("blast-radius")
    @click.option("--org", required=True)
    @click.option("--actor", required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def sim_blast(org: str, actor: str, json_mode: bool) -> None:
        from responsibleai.sovereign.cli import blast_radius

        click.get_current_context().invoke(blast_radius, org=org, actor=actor, json_mode=json_mode)

    @main.command("gauntlet")
    @click.option("--org", required=True)
    @click.option("--probe", multiple=True)
    @click.option("--json", "json_mode", is_flag=True)
    def gauntlet_top(org: str, probe: tuple[str, ...], json_mode: bool) -> None:
        cli_core.run_async(cli_core.cmd_gauntlet(org, list(probe), json_mode))

    @main.command("replay")
    @click.option("--json", "json_mode", is_flag=True)
    def replay_top(json_mode: bool) -> None:
        cli_core.emit(
            {"disposition": "UNAVAILABLE", "reason": "historical replay requires evidence context"},
            None,
            json_mode,
        )
        raise SystemExit(EXIT_UNAVAILABLE)

    @main.command("prove")
    @click.option("--json", "json_mode", is_flag=True)
    def prove_top(json_mode: bool) -> None:
        cli_core.emit(
            {"disposition": "UNAVAILABLE", "reason": "prove export not yet bound to capsule CLI"},
            None,
            json_mode,
        )
        raise SystemExit(EXIT_UNAVAILABLE)

    @main.group("policy")
    def policy_top() -> None:
        pass

    @policy_top.command("lint")
    @click.option("--json", "json_mode", is_flag=True)
    def policy_lint_unavail(json_mode: bool) -> None:
        cli_core.emit({"disposition": "UNAVAILABLE", "reason": "pass rules via API or sovereign policy lint"}, None, json_mode)
        raise SystemExit(EXIT_UNAVAILABLE)

    @main.group("capsule")
    def capsule_top() -> None:
        pass

    @capsule_top.command("create")
    @click.option("--org", required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def capsule_create(org: str, json_mode: bool) -> None:
        from responsibleai.sovereign.capsule import create_capsule

        cap = create_capsule(cli_core.ctx_from(org))
        cli_core.emit(redact_for_debugger(cap.model_dump()), None, json_mode)

    @capsule_top.command("validate")
    @click.option("--org", required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def capsule_validate(org: str, json_mode: bool) -> None:
        from responsibleai.sovereign.capsule import create_capsule
        from responsibleai.sovereign.service import SovereignService

        cap = create_capsule(cli_core.ctx_from(org))
        cli_core.emit({"valid": SovereignService().validate_capsule(cap)}, None, json_mode)

    @main.command("sandbox")
    @click.option("--json", "json_mode", is_flag=True)
    def sandbox_top(json_mode: bool) -> None:
        from responsibleai.sovereign.cli import sandbox_cmd

        click.get_current_context().invoke(sandbox_cmd, json_mode=json_mode)
