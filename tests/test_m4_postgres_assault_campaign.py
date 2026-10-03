# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 PostgreSQL assault index — enterprise concurrency on real PG when available."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

from tests.pg_test_url import resolve_admin_url_sync

M4_PG_MODULES: tuple[str, ...] = (
    "tests.test_auth_real_postgres",
    "tests.test_phase5_postgres_concurrency",
    "tests.test_phase7a_authority_kernel",
    "tests.test_pg_security_preservation",
)

M4_PG_PYTEST_TARGETS: tuple[str, ...] = (
    "tests/test_phase7a_authority_kernel.py::test_expired_lease_fails_cas",
    "tests/test_phase7a_authority_kernel.py::test_lease_reacquisition_advances_generation",
    "tests/test_phase5_postgres_concurrency.py",
)


@pytest.mark.parametrize("module_name", M4_PG_MODULES)
def test_m4_pg_assault_module_importable(module_name: str) -> None:
    importlib.import_module(module_name)


def test_m4_isolated_postgres_reachable_or_skip() -> None:
    try:
        resolve_admin_url_sync()
    except RuntimeError as exc:
        pytest.skip(f"isolated PostgreSQL not reachable: {exc}")


@pytest.mark.m4_postgres_assault
def test_m4_postgres_assault_battery() -> None:
    """Run high-value PG concurrency suites when isolated PG is up."""
    try:
        resolve_admin_url_sync()
    except RuntimeError as exc:
        pytest.skip(f"isolated PostgreSQL not reachable: {exc}")

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *M4_PG_PYTEST_TARGETS,
        "-q",
        "--no-cov",
    ]
    proc = subprocess.run(
        cmd, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
