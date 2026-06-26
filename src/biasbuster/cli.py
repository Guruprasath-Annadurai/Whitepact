from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from biasbuster.core.result import ProbeResult, SuiteResult
from biasbuster.core.runner import BiasBusterRunner
from biasbuster.probes.age_bias import AgeBiasProbe
from biasbuster.probes.cultural_bias import CulturalBiasProbe
from biasbuster.probes.gender_bias import GenderBiasProbe
from biasbuster.probes.occupational_stereotype import OccupationalStereotypeProbe
from biasbuster.probes.racial_bias import RacialBiasProbe
from biasbuster.probes.religious_bias import ReligiousBiasProbe
from biasbuster.reporting.html_reporter import HtmlReporter
from biasbuster.reporting.json_reporter import JsonReporter

load_dotenv()

console = Console()

PROBE_REGISTRY = {
    "gender-bias": GenderBiasProbe,
    "racial-bias": RacialBiasProbe,
    "occupational-stereotype": OccupationalStereotypeProbe,
    "age-bias": AgeBiasProbe,
    "religious-bias": ReligiousBiasProbe,
    "cultural-bias": CulturalBiasProbe,
}

PROVIDER_CHOICES = ["openai", "anthropic", "ollama", "huggingface"]

SEVERITY_COLORS = {
    "none": "green",
    "low": "yellow",
    "medium": "dark_orange",
    "high": "red",
    "critical": "bold red",
}


def _build_provider(provider: str, model: str | None) -> object:

    if provider == "openai":
        from biasbuster.providers.openai_provider import OpenAIProvider

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            console.print("[red]OPENAI_API_KEY not set.[/]")
            sys.exit(1)
        return OpenAIProvider(api_key=api_key, model=model or "gpt-4o")

    if provider == "anthropic":
        from biasbuster.providers.anthropic_provider import AnthropicProvider

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            console.print("[red]ANTHROPIC_API_KEY not set.[/]")
            sys.exit(1)
        return AnthropicProvider(api_key=api_key, model=model or "claude-3-5-sonnet-20241022")

    if provider == "ollama":
        from biasbuster.providers.huggingface_provider import OllamaProvider

        return OllamaProvider(model=model or "llama3.2")

    if provider == "huggingface":
        from biasbuster.providers.huggingface_provider import HuggingFaceProvider

        return HuggingFaceProvider(model=model or "microsoft/Phi-3-mini-4k-instruct")

    console.print(f"[red]Unknown provider: {provider}[/]")
    sys.exit(1)


def _print_suite_result(suite: SuiteResult) -> None:
    color = SEVERITY_COLORS.get(suite.probe_results[0].severity if suite.probe_results else "none", "white")

    console.print()
    console.print(
        Panel.fit(
            f"[bold]BiasBuster Report[/]\n"
            f"Provider: [cyan]{suite.provider_name}[/] · Model: [cyan]{suite.model_name}[/]\n"
            f"Overall score: [{color}]{suite.overall_score:.4f}[/]  "
            f"Status: {'[green]PASSED[/]' if suite.passed else '[red]FAILED[/]'}",
            border_style="dim",
        )
    )

    for probe_result in suite.probe_results:
        _print_probe_result(probe_result)


def _print_probe_result(result: ProbeResult) -> None:
    sev_color = SEVERITY_COLORS.get(result.severity, "white")

    table = Table(
        title=f"[bold]{result.probe_name}[/]  [{sev_color}]{result.severity.upper()}[/]  "
              f"score={result.overall_score:.4f}  threshold={result.threshold}",
        box=box.SIMPLE_HEAVY,
        show_lines=True,
        highlight=True,
    )
    table.add_column("Template", style="dim", max_width=45, overflow="fold")
    table.add_column("Score", justify="right", width=8)
    table.add_column("Severity", width=10)
    table.add_column("Divergent pair", width=22)

    for tr in result.template_results:
        tr_color = SEVERITY_COLORS.get(tr.severity, "white")
        pair_str = " vs ".join(tr.most_divergent_pair) if tr.most_divergent_pair else "—"
        table.add_row(
            tr.template[:80],
            f"[{tr_color}]{tr.divergence_score:.4f}[/]",
            f"[{tr_color}]{tr.severity}[/]",
            pair_str,
        )

    console.print(table)


@click.group()
@click.version_option()
def main() -> None:
    """BiasBuster — open-source bias testing for LLMs."""


@main.command()
@click.option(
    "--provider",
    type=click.Choice(PROVIDER_CHOICES),
    required=True,
    help="LLM provider to test.",
)
@click.option("--model", default=None, help="Model name (provider default if omitted).")
@click.option(
    "--probes",
    default="gender-bias",
    help="Comma-separated probe names. Available: " + ", ".join(PROBE_REGISTRY),
)
@click.option("--output", "-o", default=None, help="Save report to this path.")
@click.option("--threshold", default=None, type=float, help="Override the pass/fail threshold.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress rich output, print JSON only.")
@click.option(
    "--format",
    "fmt",
    default="json",
    type=click.Choice(["json", "html", "both"]),
    help="Report format: json (default), html, or both.",
)
def run(
    provider: str,
    model: str | None,
    probes: str,
    output: str | None,
    threshold: float | None,
    quiet: bool,
    fmt: str,
) -> None:
    """Run bias probes against an LLM provider."""
    probe_names = [p.strip() for p in probes.split(",")]
    unknown = [p for p in probe_names if p not in PROBE_REGISTRY]
    if unknown:
        console.print(f"[red]Unknown probes: {', '.join(unknown)}[/]")
        console.print(f"Available: {', '.join(PROBE_REGISTRY)}")
        sys.exit(1)

    built_probes = [
        PROBE_REGISTRY[name](threshold=threshold) for name in probe_names
    ]
    built_provider = _build_provider(provider, model)

    if not quiet:
        console.print(
            f"\n[bold cyan]BiasBuster[/] running [bold]{', '.join(probe_names)}[/] "
            f"against [bold]{provider}[/] / [bold]{model or 'default'}[/] …\n"
        )

    runner = BiasBusterRunner(provider=built_provider)  # type: ignore[arg-type]
    suite = asyncio.run(runner.run(built_probes))

    if quiet:
        JsonReporter().print(suite)
    else:
        _print_suite_result(suite)

    if output:
        base = Path(output)
        if fmt in ("json", "both"):
            json_path = base.with_suffix(".json") if base.suffix != ".json" else base
            JsonReporter().save(suite, json_path)
            if not quiet:
                console.print(f"\n[dim]JSON report saved to {json_path}[/]")
        if fmt in ("html", "both"):
            html_path = base.with_suffix(".html")
            HtmlReporter().save(suite, html_path)
            if not quiet:
                console.print(f"[dim]HTML report saved to {html_path}[/]")

    sys.exit(0 if suite.passed else 1)


@main.command(name="list-probes")
def list_probes() -> None:
    """List all available bias probes."""
    table = Table(title="Available probes", box=box.SIMPLE)
    table.add_column("Name", style="cyan")
    table.add_column("Default threshold", justify="right")
    table.add_column("Description")

    for name, cls in PROBE_REGISTRY.items():
        table.add_row(name, str(cls.default_threshold), cls.description)

    console.print(table)
