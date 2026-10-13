# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M6 final engineering campaign — lineage, regression indexes, release readiness."""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent

QUALIFIED_M5 = "46685fad1ad49cfde36341ea1fad146ce1d2e714"
QUALIFIED_M4 = "52d9b3c5497af24bb7d4a7147e33deaadc64296e"
QUALIFIED_M3 = "620399b7973f5ed058d45218610be228e72d3ed8"

M6_REGRESSION_MODULES: tuple[str, ...] = (
    "tests.test_m6_auth_not_authority",
    "tests.test_m6_approval_not_authority_manufacture",
    "tests.test_m6_duplicate_execution_index",
    "tests.test_m6_cross_tenant_index",
    "tests.test_m6_failure_combination_index",
    "tests.test_m5_integrated_regression_campaign",
    "tests.test_m5_integrated_rc_gate",
    "tests.test_m4_hostile_regression_campaign",
    "tests.test_m4_m123_regression_index",
    "tests.test_m5_unknown_outcome_regression",
    "tests.test_m5_revocation_stress_matrix",
    "tests.test_m5_mcp_regression_index",
    "tests.test_m5_chaos_campaign_matrix",
    "tests.test_totp_matched_counter_security",
    "tests.test_v1_exactly_one_effect",
    "tests.test_mcp_ws2_authority_matrix",
)

M6_DOC_ANCHORS: tuple[str, ...] = (
    "docs/enterprise/M6_DEFECT_REGISTER.md",
    "docs/enterprise/FINAL_AUTHORITY_PATH_PROOF.md",
    "docs/enterprise/FINAL_FAIL_CLOSED_MATRIX.md",
    "docs/enterprise/FINAL_CLAIMS_MATRIX.md",
    "docs/enterprise/KNOWN_LIMITATIONS.md",
    "docs/enterprise/FINAL_ARTIFACT_INVENTORY.md",
    "docs/enterprise/FINAL_RELEASE_CHECKLIST.md",
    "docs/enterprise/M6_FINAL_ANTIGRAVITY_HANDOFF.md",
    "docs/enterprise/M6_VERSION_AUDIT.md",
)


def test_m6_qualified_m5_ancestor_recorded() -> None:
    freeze = REPO / "docs" / "enterprise" / "M6_DEFECT_REGISTER.md"
    text = freeze.read_text(encoding="utf-8")
    assert QUALIFIED_M5[:12] in text
    assert "VERIFIED_CLOSED" in text


def test_m6_git_ancestry_from_qualified_m5() -> None:
    verify = subprocess.run(
        ["git", "rev-parse", "--verify", f"{QUALIFIED_M5}^{{commit}}"],
        cwd=REPO,
        capture_output=True,
    )
    if verify.returncode != 0:
        pytest.skip("Qualified M5 object not present (shallow CI checkout)")

    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", QUALIFIED_M5, "HEAD"],
        cwd=REPO,
        capture_output=True,
    )
    assert result.returncode == 0, "HEAD must descend from qualified M5"


@pytest.mark.parametrize("module_name", M6_REGRESSION_MODULES)
def test_m6_regression_module_importable(module_name: str) -> None:
    importlib.import_module(module_name)


@pytest.mark.parametrize("relpath", M6_DOC_ANCHORS)
def test_m6_documentation_anchor_present(relpath: str) -> None:
    assert (REPO / relpath).is_file(), relpath


def test_m6_version_metadata_coherent() -> None:
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "1.3.1"' in pyproject
    assert "whitepact" in pyproject
    assert "rai-governance-platform" in pyproject


def test_m6_m5_m4_m3_shas_documented_in_handoff() -> None:
    handoff = (REPO / "docs" / "enterprise" / "M6_FINAL_ANTIGRAVITY_HANDOFF.md").read_text(
        encoding="utf-8"
    )
    assert QUALIFIED_M5 in handoff
    assert QUALIFIED_M4 in handoff
    assert QUALIFIED_M3 in handoff
