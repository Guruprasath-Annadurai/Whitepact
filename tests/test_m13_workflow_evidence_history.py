# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Jobs reading immutable historical evidence must actually fetch that evidence."""

from pathlib import Path

import pytest
import yaml


@pytest.mark.parametrize(
    ("workflow", "job"),
    [
        ("m13i1-integration.yml", "independent-security"),
        ("m13-absolute-enrollment-review.yml", "qualification"),
        ("m13-absolute-full-suite.yml", "test"),
    ],
)
def test_historical_provenance_jobs_fetch_full_history(workflow, job):
    path = Path(__file__).resolve().parents[1] / ".github/workflows" / workflow
    definition = yaml.safe_load(path.read_text())
    checkouts = [
        step
        for step in definition["jobs"][job]["steps"]
        if step.get("uses", "").startswith("actions/checkout@")
    ]
    assert len(checkouts) == 1
    assert checkouts[0].get("with", {}).get("fetch-depth") == 0
    assert checkouts[0]["with"]["persist-credentials"] is False
