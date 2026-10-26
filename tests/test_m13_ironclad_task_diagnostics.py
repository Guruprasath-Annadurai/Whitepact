# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Ensure teardown observation does not replace application cancellation semantics."""

import asyncio
import asyncio.runners
import io
import json

import pytest
from scripts.engineering.m13_ironclad_task_diagnostics import runner_diagnostics


def test_observes_delayed_cancellation_without_recancelling_or_leaking_timers() -> None:
    output = io.StringIO()
    cancellations = []
    original = asyncio.runners._cancel_all_tasks
    loop = asyncio.new_event_loop()

    async def owned_worker() -> None:
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancellations.append(asyncio.current_task().cancelling())
            await asyncio.sleep(0.03)
            raise

    try:
        worker = loop.create_task(owned_worker(), name="owned-worker")
        loop.run_until_complete(asyncio.sleep(0))
        with runner_diagnostics(stream=output, delays=(0.001, 60)):
            asyncio.runners._cancel_all_tasks(loop)
        assert asyncio.runners._cancel_all_tasks is original
        assert worker.cancelled()
        assert cancellations == [1]
        assert not asyncio.all_tasks(loop)
        assert all(handle.cancelled() for handle in loop._scheduled)
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        task = next(row for row in records if row["event"] == "runner_teardown_task")
        assert task["name"] == "owned-worker"
        assert task["cancelling"] == 1
        assert task["waiter_type"] == "Future"
        assert any(row["event"] == "runner_teardown_frame" for row in records)
        assert records[-1]["diagnostic_timers_cancelled"] == 2
    finally:
        loop.close()


def test_restores_runner_function_when_original_raises(monkeypatch) -> None:
    output = io.StringIO()
    loop = asyncio.new_event_loop()

    def original(_loop) -> None:
        raise RuntimeError("original failure")

    monkeypatch.setattr(asyncio.runners, "_cancel_all_tasks", original)
    try:
        with pytest.raises(RuntimeError, match="original failure"):
            with runner_diagnostics(stream=output, delays=(60,)):
                asyncio.runners._cancel_all_tasks(loop)
        assert asyncio.runners._cancel_all_tasks is original
        assert all(handle.cancelled() for handle in loop._scheduled)
    finally:
        loop.close()
