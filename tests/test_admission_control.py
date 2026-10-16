# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Admission control sheds excess concurrency immediately and never leaks a slot."""

from __future__ import annotations

import asyncio

import pytest

from responsibleai.ops.admission import AdmissionControlMiddleware


def _scope(path: str = "/api/x", kind: str = "http") -> dict:
    return {"type": kind, "path": path, "headers": []}


class _Recorder:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def __call__(self, message: dict) -> None:
        self.messages.append(message)

    @property
    def status(self) -> int:
        return next(m["status"] for m in self.messages if m["type"] == "http.response.start")


async def _noop_receive():  # pragma: no cover
    return {"type": "http.request"}


def _gate_app(gate: asyncio.Event, entered: list[int], fail: bool = False):
    async def app(scope, receive, send):
        entered.append(1)
        await gate.wait()
        if fail:
            raise RuntimeError("handler exploded")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    return app


async def test_excess_requests_get_an_immediate_503_with_retry_after() -> None:
    gate, entered = asyncio.Event(), []
    mw = AdmissionControlMiddleware(_gate_app(gate, entered), max_inflight=2, retry_after_seconds=3)
    held = [asyncio.create_task(mw(_scope(), _noop_receive, _Recorder())) for _ in range(2)]
    await asyncio.sleep(0.01)
    assert mw.inflight == 2
    rec = _Recorder()
    await asyncio.wait_for(mw(_scope(), _noop_receive, rec), timeout=0.5)  # returns without waiting
    assert rec.status == 503
    start = next(m for m in rec.messages if m["type"] == "http.response.start")
    assert (b"retry-after", b"3") in start["headers"]
    assert len(entered) == 2  # no work was started for the shed request
    assert mw.shed_total == 1
    gate.set()
    await asyncio.gather(*held)
    assert mw.inflight == 0
    ok = _Recorder()
    await mw(_scope(), _noop_receive, ok)
    assert ok.status == 200  # capacity returns once requests finish


async def test_a_failing_handler_releases_its_slot() -> None:
    gate, entered = asyncio.Event(), []
    gate.set()
    mw = AdmissionControlMiddleware(_gate_app(gate, entered, fail=True), max_inflight=1)
    for _ in range(5):
        with pytest.raises(RuntimeError):
            await mw(_scope(), _noop_receive, _Recorder())
    assert mw.inflight == 0 and mw.shed_total == 0


async def test_a_cancelled_request_releases_its_slot() -> None:
    gate, entered = asyncio.Event(), []
    mw = AdmissionControlMiddleware(_gate_app(gate, entered), max_inflight=1)
    task = asyncio.create_task(mw(_scope(), _noop_receive, _Recorder()))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert mw.inflight == 0


@pytest.mark.parametrize("path", ["/health", "/ready", "/sse"])
async def test_liveness_readiness_and_streams_are_never_shed(path: str) -> None:
    gate, entered = asyncio.Event(), []
    mw = AdmissionControlMiddleware(_gate_app(gate, entered), max_inflight=1)
    held = asyncio.create_task(mw(_scope(), _noop_receive, _Recorder()))
    await asyncio.sleep(0.01)
    probe = asyncio.create_task(mw(_scope(path), _noop_receive, _Recorder()))
    await asyncio.sleep(0.01)
    assert len(entered) == 2 and mw.shed_total == 0
    gate.set()
    await asyncio.gather(held, probe)


async def test_zero_disables_and_non_http_scopes_pass_through() -> None:
    gate, entered = asyncio.Event(), []
    gate.set()
    off = AdmissionControlMiddleware(_gate_app(gate, entered), max_inflight=0)
    await asyncio.gather(*[off(_scope(), _noop_receive, _Recorder()) for _ in range(20)])
    assert len(entered) == 20
    on = AdmissionControlMiddleware(_gate_app(gate, entered), max_inflight=1)
    await on({"type": "lifespan"}, _noop_receive, _Recorder())  # not counted, not shed
    assert on.inflight == 0


def test_negative_limit_is_rejected() -> None:
    with pytest.raises(ValueError):
        AdmissionControlMiddleware(lambda *a: None, max_inflight=-1)  # type: ignore[arg-type]
