# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Top-level whitepact command aliases → shared cli_core implementations."""

from __future__ import annotations

from pathlib import Path

import click

from responsibleai.sovereign import cli_core


def register_top_level_aliases(main: click.Group) -> None:
    @main.command("doctor")
    @click.option("--org")
    @click.option("--manifest", type=click.Path(path_type=Path))
    @click.option("--remote", is_flag=True, help="Probe saved base URL. Does not send credentials.")
    @click.option("--json", "json_mode", is_flag=True)
    def doctor_top(org: str | None, manifest: Path | None, remote: bool, json_mode: bool) -> None:
        cli_core.run_async(
            cli_core.cmd_doctor(org, manifest, json_mode, remote=remote),
            json_mode=json_mode,
        )

    @main.command("ci")
    @click.option("--manifest", type=click.Path(exists=True, path_type=Path), required=True)
    @click.option("--org", required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def ci_top(manifest: Path, org: str, json_mode: bool) -> None:
        cli_core.run_async(cli_core.cmd_ci(manifest, org, json_mode), json_mode=json_mode)

    @main.command("xray")
    @click.option("--org", required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def xray_top(org: str, json_mode: bool) -> None:
        cli_core.run_async(cli_core.cmd_xray(org, json_mode), json_mode=json_mode)

    @main.command("trace")
    @click.option("--org", required=True)
    @click.option("--evidence", required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def trace_top(org: str, evidence: str, json_mode: bool) -> None:
        cli_core.run_async(cli_core.cmd_trace(org, evidence, json_mode), json_mode=json_mode)

    @main.command("explain")
    @click.option("--org", required=True)
    @click.option("--evidence")
    @click.option("--identity")
    @click.option("--json", "json_mode", is_flag=True)
    def explain_top(org: str, evidence: str | None, identity: str | None, json_mode: bool) -> None:
        cli_core.run_async(
            cli_core.cmd_explain(org, evidence, identity, json_mode), json_mode=json_mode
        )

    @main.group("authority")
    def authority_group() -> None:
        pass

    @authority_group.command("compare")
    @click.option("--org", required=True)
    @click.option("--manifest", type=click.Path(exists=True, path_type=Path), required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def authority_compare(org: str, manifest: Path, json_mode: bool) -> None:
        cli_core.run_async(
            cli_core.cmd_authority_compare(org, manifest, json_mode), json_mode=json_mode
        )

    @authority_group.command("drift")
    @click.option("--org", required=True)
    @click.option("--manifest", type=click.Path(exists=True, path_type=Path), required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def authority_drift(org: str, manifest: Path, json_mode: bool) -> None:
        cli_core.run_async(
            cli_core.cmd_authority_drift(org, manifest, json_mode), json_mode=json_mode
        )

    @authority_group.command("diff")
    @click.option("--org", required=True)
    @click.option("--manifest", type=click.Path(exists=True, path_type=Path), required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def authority_diff(org: str, manifest: Path, json_mode: bool) -> None:
        cli_core.run_async(
            cli_core.cmd_authority_diff(org, manifest, json_mode), json_mode=json_mode
        )

    @main.group("simulate")
    def simulate_top() -> None:
        pass

    @simulate_top.command("blast-radius")
    @click.option("--org", required=True)
    @click.option("--actor", required=True)
    @click.option("--extra-cap", multiple=True)
    @click.option("--json", "json_mode", is_flag=True)
    def sim_blast(org: str, actor: str, extra_cap: tuple[str, ...], json_mode: bool) -> None:
        cli_core.run_async(
            cli_core.cmd_blast_radius(org, actor, extra_cap, json_mode), json_mode=json_mode
        )

    @simulate_top.command("mission")
    @click.option("--org", required=True)
    @click.option("--agent", required=True)
    @click.option("--step", "steps", multiple=True, required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def sim_mission(org: str, agent: str, steps: tuple[str, ...], json_mode: bool) -> None:
        cli_core.run_async(
            cli_core.cmd_mission(org, agent, list(steps), json_mode), json_mode=json_mode
        )

    @main.command("shadow")
    @click.option("--org", required=True)
    @click.option("--agent", required=True)
    @click.option("--action", required=True)
    @click.option("--persist", is_flag=True)
    @click.option("--json", "json_mode", is_flag=True)
    def shadow_top(org: str, agent: str, action: str, persist: bool, json_mode: bool) -> None:
        cli_core.run_async(
            cli_core.cmd_shadow(org, agent, action, persist, json_mode), json_mode=json_mode
        )

    @main.command("gauntlet")
    @click.option("--org", required=True)
    @click.option("--probe", multiple=True)
    @click.option("--json", "json_mode", is_flag=True)
    def gauntlet_top(org: str, probe: tuple[str, ...], json_mode: bool) -> None:
        cli_core.run_async(cli_core.cmd_gauntlet(org, list(probe), json_mode), json_mode=json_mode)

    @main.command("replay")
    @click.option("--file", "evidence_file", type=click.Path(path_type=Path), required=True)
    @click.option("--org", help="Local tenant label. Must match the evidence tenant.")
    @click.option("--json", "json_mode", is_flag=True)
    def replay_top(evidence_file: Path, org: str | None, json_mode: bool) -> None:
        """Reconstruct and validate stored evidence. Does not re-execute anything."""
        cli_core.run_async(
            cli_core.cmd_replay(evidence_file, org, json_mode),
            json_mode=json_mode,
        )

    @main.command("prove")
    @click.option("--file", "evidence_file", type=click.Path(path_type=Path), required=True)
    @click.option("--org", help="Local tenant label. Must match the evidence tenant.")
    @click.option("--output", type=click.Path(path_type=Path))
    @click.option("--json", "json_mode", is_flag=True)
    def prove_top(
        evidence_file: Path, org: str | None, output: Path | None, json_mode: bool
    ) -> None:
        """Export a verification artifact from stored evidence. Does not invent fields."""
        cli_core.run_async(
            cli_core.cmd_prove(evidence_file, org, output, json_mode),
            json_mode=json_mode,
        )

    @main.group("policy")
    def policy_top() -> None:
        pass

    @policy_top.command("lint")
    @click.option("--org", required=True)
    @click.option("--rules-file", type=click.Path(exists=True, path_type=Path))
    @click.option("--rules-json")
    @click.option("--json", "json_mode", is_flag=True)
    def policy_lint(
        org: str, rules_file: Path | None, rules_json: str | None, json_mode: bool
    ) -> None:
        cli_core.run_async(
            cli_core.cmd_policy_lint(org, rules_file, rules_json, json_mode), json_mode=json_mode
        )

    @policy_top.command("validate")
    @click.option("--org", required=True)
    @click.option("--rules-file", type=click.Path(exists=True, path_type=Path))
    @click.option("--rules-json")
    @click.option("--json", "json_mode", is_flag=True)
    def policy_validate(
        org: str, rules_file: Path | None, rules_json: str | None, json_mode: bool
    ) -> None:
        cli_core.run_async(
            cli_core.cmd_policy_validate(org, rules_file, rules_json, json_mode),
            json_mode=json_mode,
        )

    @policy_top.command("test")
    @click.option("--org", required=True)
    @click.option("--cases-file", type=click.Path(exists=True, path_type=Path))
    @click.option("--cases-json")
    @click.option("--json", "json_mode", is_flag=True)
    def policy_test(
        org: str, cases_file: Path | None, cases_json: str | None, json_mode: bool
    ) -> None:
        cli_core.run_async(
            cli_core.cmd_policy_test(org, cases_file, cases_json, json_mode), json_mode=json_mode
        )

    @policy_top.command("diff")
    @click.option("--org", required=True)
    @click.option("--rules-file", type=click.Path(exists=True, path_type=Path))
    @click.option("--rules-json")
    @click.option("--json", "json_mode", is_flag=True)
    def policy_diff(
        org: str, rules_file: Path | None, rules_json: str | None, json_mode: bool
    ) -> None:
        cli_core.run_async(
            cli_core.cmd_policy_diff(org, rules_file, rules_json, json_mode), json_mode=json_mode
        )

    @policy_top.command("simulate")
    @click.option("--org", required=True)
    @click.option("--rules-file", type=click.Path(exists=True, path_type=Path))
    @click.option("--rules-json")
    @click.option("--action", "actions", multiple=True, required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def policy_simulate(
        org: str,
        rules_file: Path | None,
        rules_json: str | None,
        actions: tuple[str, ...],
        json_mode: bool,
    ) -> None:
        cli_core.run_async(
            cli_core.cmd_policy_simulate(org, rules_file, rules_json, list(actions), json_mode),
            json_mode=json_mode,
        )

    @main.group("capsule")
    def capsule_top() -> None:
        pass

    @capsule_top.command("create")
    @click.option("--org", required=True)
    @click.option("--json", "json_mode", is_flag=True)
    def capsule_create(org: str, json_mode: bool) -> None:
        cli_core.run_async(cli_core.cmd_capsule_create(org, json_mode), json_mode=json_mode)

    @capsule_top.command("inspect")
    @click.option(
        "--capsule", "capsule_file", type=click.Path(exists=True, path_type=Path), required=True
    )
    @click.option("--json", "json_mode", is_flag=True)
    def capsule_inspect(capsule_file: Path, json_mode: bool) -> None:
        cli_core.run_async(
            cli_core.cmd_capsule_inspect(capsule_file, json_mode), json_mode=json_mode
        )

    @capsule_top.command("validate")
    @click.option("--org")
    @click.option("--capsule", "capsule_file", type=click.Path(exists=True, path_type=Path))
    @click.option("--json", "json_mode", is_flag=True)
    def capsule_validate(org: str | None, capsule_file: Path | None, json_mode: bool) -> None:
        cli_core.run_async(
            cli_core.cmd_capsule_validate(capsule_file, org, json_mode), json_mode=json_mode
        )

    @capsule_top.command("reproduce")
    @click.option(
        "--capsule", "capsule_file", type=click.Path(exists=True, path_type=Path), required=True
    )
    @click.option("--json", "json_mode", is_flag=True)
    def capsule_reproduce(capsule_file: Path, json_mode: bool) -> None:
        cli_core.run_async(
            cli_core.cmd_capsule_reproduce(capsule_file, json_mode), json_mode=json_mode
        )

    @main.command("sandbox")
    @click.option("--json", "json_mode", is_flag=True)
    def sandbox_top(json_mode: bool) -> None:
        cli_core.run_async(cli_core.cmd_sandbox(json_mode), json_mode=json_mode)
