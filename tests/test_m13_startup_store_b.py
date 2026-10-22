# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Missing/unreadable/corrupt Store B cannot be repaired by Store A reconnection."""

import pytest
from sqlalchemy import func, select, text

from responsibleai.data_governance.backup_defense import (
    RestoreQuarantineError,
    RestoreReadinessState,
    get_restore_readiness_gate,
    set_restore_readiness_gate,
)
from responsibleai.db.engine import governance_execution_authorizations
from responsibleai.mcp.server import _call_tool
from tests.test_m13_final_admission import admission_engine as admission_engine


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "unavailable_location", "corrupt"])
async def test_store_b_failure_denies_before_and_after_database_reconnection(
    failure, admission_engine, monkeypatch, tmp_path
):
    monkeypatch.setenv("WHITEPACT_RESTORE_MODE", "1")
    monkeypatch.delenv("WHITEPACT_STORE_B_PATH", raising=False)
    monkeypatch.delenv("WHITEPACT_LIFECYCLE_STORE_PATH", raising=False)
    path = tmp_path / "store-b"
    if failure == "unavailable_location":
        path.mkdir()
        monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(path))
    elif failure == "corrupt":
        path.write_bytes(b"invalid-store-b-negative-fixture")
        path.chmod(0o600)
        monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(path))
    evidence = tmp_path / "unresolved-negative-evidence"
    evidence.write_bytes(b"test-owned marker; not a containment receipt")
    set_restore_readiness_gate(None)
    try:
        gate = get_restore_readiness_gate()
        assert gate.state == RestoreReadinessState.FAILED
        assert gate.provider_error
        query = select(func.count()).select_from(governance_execution_authorizations)
        async with admission_engine.raw.connect() as conn:
            before = await conn.scalar(query)
        for _ in range(2):
            with pytest.raises(RestoreQuarantineError):
                await gate.assert_current_traffic_admitted(admission_engine)
            _, payload = await _call_tool(
                "calculate_cost", {"model": "gpt-4o", "input_tokens": 1, "output_tokens": 1}
            )
            assert payload["error"] == "restore_quarantine"
            assert evidence.read_bytes() == b"test-owned marker; not a containment receipt"
            if admission_engine.raw.dialect.name == "postgresql":
                await admission_engine.raw.dispose()
            async with admission_engine.raw.connect() as conn:
                assert await conn.scalar(text("SELECT 1")) == 1
                assert await conn.scalar(query) == before
            assert gate.state == RestoreReadinessState.FAILED
        set_restore_readiness_gate(None)
        assert get_restore_readiness_gate().state == RestoreReadinessState.FAILED
        if failure == "corrupt":
            assert path.read_bytes() == b"invalid-store-b-negative-fixture"
    finally:
        set_restore_readiness_gate(None)
