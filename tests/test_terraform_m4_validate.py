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


@pytest.mark.skipif(shutil.which("terraform") is None, reason="terraform CLI not installed")
def test_optional_gcp_staging_module_rejects_null_kms_and_validates() -> None:
    """Optional DR bucket must validate without a null CMEK argument.

    Provider 5.x treats ``default_kms_key_name = null`` as an omitted
    required argument. The module must not invent a key. Omitting the
    encryption block keeps Google-managed encryption, versioning, and
    uniform access.
    """
    module = TF_ROOT / "modules" / "gcp-staging-optional"
    source = (module / "main.tf").read_text(encoding="utf-8")
    assert "encryption {" not in source
    assert "versioning" in source
    assert "uniform_bucket_level_access = true" in source
    assert "force_destroy               = false" in source
    init = subprocess.run(
        ["terraform", "init", "-backend=false"],
        cwd=module,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init.returncode == 0, init.stderr
    validate = subprocess.run(
        ["terraform", "validate"],
        cwd=module,
        capture_output=True,
        text=True,
        check=False,
    )
    assert validate.returncode == 0, validate.stderr


def test_cloud_terraform_tree_present() -> None:
    assert (TF_ROOT / "versions.tf").is_file()
    assert (TF_ROOT / "environments" / "production" / "main.tf").is_file()
    assert (TF_ROOT / "modules" / "cloudflare-edge" / "main.tf").is_file()
