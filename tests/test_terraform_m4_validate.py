# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 — Terraform plan-only validation (no apply)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TF_ROOT = ROOT / "infra" / "terraform"
MODULE = TF_ROOT / "modules" / "whitepact-hetzner-foundation"


@pytest.mark.skipif(shutil.which("terraform") is None, reason="terraform CLI not installed")
def test_hetzner_foundation_module_validates() -> None:
    init = subprocess.run(
        ["terraform", "init", "-backend=false"],
        cwd=MODULE,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init.returncode == 0, init.stderr
    validate = subprocess.run(
        ["terraform", "validate"],
        cwd=MODULE,
        capture_output=True,
        text=True,
        check=False,
    )
    assert validate.returncode == 0, validate.stderr


def test_cloud_terraform_tree_present() -> None:
    assert (TF_ROOT / "versions.tf").is_file()
    assert (TF_ROOT / "environments" / "production" / "main.tf").is_file()
    assert (TF_ROOT / "modules" / "cloudflare-edge" / "main.tf").is_file()
