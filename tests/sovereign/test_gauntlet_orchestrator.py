# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from responsibleai.sovereign.gauntlet_orchestrator import (
    GauntletCaseStatus,
    run_registered_gauntlet,
)


def test_gauntlet_runs_in_memory_probe() -> None:
    report = run_registered_gauntlet("org-1", probe_ids=["tenant_guard"])
    assert len(report.cases) == 1
    assert report.cases[0].status in (
        GauntletCaseStatus.PASS,
        GauntletCaseStatus.FAIL,
        GauntletCaseStatus.ERROR,
    )
    assert report.cases[0].status != GauntletCaseStatus.UNAVAILABLE
