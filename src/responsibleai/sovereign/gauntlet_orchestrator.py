# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Execute registered Gauntlet probes via pytest (observed PASS/FAIL only)."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from responsibleai.sovereign.gauntlet_registry import GAUNTLET_PROBES, GauntletProbe, ProbeRuntime

_REPO_ROOT = Path(__file__).resolve().parents[3]


class GauntletCaseStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"


class GauntletCaseResult(BaseModel):
    test_id: str
    attack_family: str
    expected_control: str
    observed_behavior: str
    status: GauntletCaseStatus
    proof_refs: list[str] = Field(default_factory=list)
    duration_ms: float
    related_ids: dict[str, str] = Field(default_factory=dict)
    diagnostic_summary: str = ""


class GauntletReport(BaseModel):
    run_id: str
    organization_id: str
    cases: list[GauntletCaseResult] = Field(default_factory=list)


def _runtime_available(runtime: ProbeRuntime) -> tuple[bool, str]:
    if runtime == ProbeRuntime.IN_MEMORY:
        return True, ""
    if runtime == ProbeRuntime.POSTGRES:
        if os.environ.get("SOVEREIGN_GAUNTLET_SKIP_PG", "").lower() in ("1", "true", "yes"):
            return False, "SOVEREIGN_GAUNTLET_SKIP_PG set"
        if os.environ.get("WHITEPACT_TEST_PG_URL"):
            return True, ""
        try:
            from tests.pg_test_url import isolated_pg_url  # noqa: F401

            return True, ""
        except Exception as exc:  # noqa: BLE001
            return False, f"postgres probe runtime unavailable: {exc}"
    if runtime == ProbeRuntime.MCP_LIVE:
        if os.environ.get("SOVEREIGN_GAUNTLET_ALLOW_MCP", "").lower() not in ("1", "true", "yes"):
            return False, "set SOVEREIGN_GAUNTLET_ALLOW_MCP=1 to run live MCP gauntlet probe"
        return True, ""
    return False, f"unknown runtime {runtime}"


def _run_pytest_probe(probe: GauntletProbe, *, timeout_s: int = 300) -> GauntletCaseResult:
    start = time.perf_counter()
    ok, reason = _runtime_available(probe.runtime)
    if not ok:
        return GauntletCaseResult(
            test_id=probe.test_id,
            attack_family=probe.attack_family,
            expected_control=probe.expected_control,
            observed_behavior=reason,
            status=GauntletCaseStatus.UNAVAILABLE,
            duration_ms=(time.perf_counter() - start) * 1000,
            diagnostic_summary=probe.diagnostic_hint or reason,
            proof_refs=[probe.pytest_nodeid],
        )

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        probe.pytest_nodeid,
        "-q",
        "--tb=line",
        "-p",
        "no:cacheprovider",
    ]
    env = os.environ.copy()
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return GauntletCaseResult(
            test_id=probe.test_id,
            attack_family=probe.attack_family,
            expected_control=probe.expected_control,
            observed_behavior="pytest probe timed out",
            status=GauntletCaseStatus.ERROR,
            duration_ms=(time.perf_counter() - start) * 1000,
            diagnostic_summary=f"timeout after {timeout_s}s",
            proof_refs=[probe.pytest_nodeid],
        )
    except OSError as exc:
        return GauntletCaseResult(
            test_id=probe.test_id,
            attack_family=probe.attack_family,
            expected_control=probe.expected_control,
            observed_behavior=f"spawn error: {exc}",
            status=GauntletCaseStatus.ERROR,
            duration_ms=(time.perf_counter() - start) * 1000,
            proof_refs=[probe.pytest_nodeid],
        )

    output = (completed.stdout or "") + (completed.stderr or "")
    duration = (time.perf_counter() - start) * 1000
    proof_refs = [probe.pytest_nodeid]
    if completed.returncode == 0:
        return GauntletCaseResult(
            test_id=probe.test_id,
            attack_family=probe.attack_family,
            expected_control=probe.expected_control,
            observed_behavior="pytest probe passed — control behavior observed",
            status=GauntletCaseStatus.PASS,
            duration_ms=duration,
            proof_refs=proof_refs,
            diagnostic_summary=output.strip()[-400:] if output else "",
        )
    if completed.returncode == 5:
        return GauntletCaseResult(
            test_id=probe.test_id,
            attack_family=probe.attack_family,
            expected_control=probe.expected_control,
            observed_behavior="no tests collected",
            status=GauntletCaseStatus.UNAVAILABLE,
            duration_ms=duration,
            proof_refs=proof_refs,
            diagnostic_summary=output.strip()[:500],
        )
    return GauntletCaseResult(
        test_id=probe.test_id,
        attack_family=probe.attack_family,
        expected_control=probe.expected_control,
        observed_behavior=f"pytest exit {completed.returncode}",
        status=GauntletCaseStatus.FAIL,
        duration_ms=duration,
        proof_refs=proof_refs,
        diagnostic_summary=output.strip()[-800:] if output else "",
    )


def run_registered_gauntlet(
    organization_id: str,
    *,
    probe_ids: list[str] | None = None,
) -> GauntletReport:
    run_id = f"gauntlet-{uuid.uuid4().hex}"
    probes = GAUNTLET_PROBES
    if probe_ids:
        wanted = set(probe_ids)
        probes = tuple(p for p in GAUNTLET_PROBES if p.test_id in wanted)
    cases = [_run_pytest_probe(probe) for probe in probes]
    return GauntletReport(run_id=run_id, organization_id=organization_id, cases=cases)
