# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.whitepact_cloud.offboarding import offboarding_complete, run_offboarding


def test_offboarding_runs_all_steps() -> None:
    calls: list[str] = []

    def audit(emp: str, event: str) -> str:
        calls.append(f"{emp}:{event}")
        return "audit-1"

    state = run_offboarding(
        "emp-9",
        revoke_session_fn=lambda e: calls.append(f"sessions:{e}"),
        revoke_grants_fn=lambda e: calls.append(f"grants:{e}"),
        revoke_provider_fn=lambda e: calls.append(f"provider:{e}"),
        audit_fn=audit,
    )
    assert offboarding_complete(state)
    assert "sessions:emp-9" in calls
    assert "grants:emp-9" in calls
