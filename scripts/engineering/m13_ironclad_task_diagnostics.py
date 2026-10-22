# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Observe asyncio runner teardown without changing its cancellation behavior.

Usage: python scripts/engineering/m13_ironclad_task_diagnostics.py [pytest args]
The caller retains responsibility for pytest's existing 120-second timeout.
Only timer handles created here are cancelled; application tasks are untouched.
"""

from __future__ import annotations

import asyncio
import asyncio.runners
import json
import sys
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from typing import IO

_DELAYS = (10.0, 30.0, 60.0, 90.0)
_MAX_TASKS = 32
_MAX_FRAMES = 8


def _emit(stream: IO[str], event: str, **fields: object) -> None:
    print(json.dumps({"event": event, **fields}, sort_keys=True), file=stream, flush=True)


def _snapshot(loop: asyncio.AbstractEventLoop, stream: IO[str], delay: float) -> None:
    """Log bounded identities/stacks, never coroutine arguments or frame locals."""
    try:
        tasks = sorted(asyncio.all_tasks(loop), key=id)
        _emit(stream, "runner_teardown_timer", delay_seconds=delay, pending=len(tasks))
        for task in tasks[:_MAX_TASKS]:
            coro = task.get_coro()
            waiter = getattr(task, "_fut_waiter", None)
            _emit(
                stream,
                "runner_teardown_task",
                identity=id(task),
                name=task.get_name()[:200],
                coroutine=getattr(coro, "__qualname__", type(coro).__qualname__),
                cancelling=task.cancelling(),
                waiter_type=type(waiter).__qualname__ if waiter is not None else None,
                waiter_done=waiter.done() if waiter is not None else None,
            )
            # File/line/function only: no locals, source lines, arguments or repr(task).
            for frame in task.get_stack(limit=_MAX_FRAMES):
                info = traceback.extract_stack(frame, limit=1)[0]
                _emit(
                    stream,
                    "runner_teardown_frame",
                    file=info.filename,
                    line=info.lineno,
                    function=info.name,
                )
        if len(tasks) > _MAX_TASKS:
            _emit(stream, "runner_teardown_truncated", omitted=len(tasks) - _MAX_TASKS)
    except Exception as exc:
        _emit(stream, "runner_teardown_diagnostic_error", error_type=type(exc).__qualname__)


@contextmanager
def runner_diagnostics(
    *, stream: IO[str] | None = None, delays: tuple[float, ...] = _DELAYS
) -> Iterator[None]:
    """Temporarily observe the original runner close; restore it even on failure."""
    output = stream if stream is not None else sys.__stderr__
    original = asyncio.runners._cancel_all_tasks

    def observed_cancel_all(loop: asyncio.AbstractEventLoop) -> None:
        handles: list[asyncio.TimerHandle] = []
        try:
            _emit(output, "runner_teardown_enter", pending=len(asyncio.all_tasks(loop)))
            for delay in delays:
                handles.append(loop.call_later(delay, _snapshot, loop, output, delay))
            # Preserve the standard library's exact cancellation and gathering path.
            original(loop)
        finally:
            for handle in handles:
                handle.cancel()
            _emit(output, "runner_teardown_exit", diagnostic_timers_cancelled=len(handles))

    asyncio.runners._cancel_all_tasks = observed_cancel_all
    try:
        yield
    finally:
        asyncio.runners._cancel_all_tasks = original


def main(args: list[str] | None = None) -> int:
    import pytest

    with runner_diagnostics():
        return int(pytest.main(sys.argv[1:] if args is None else args))


if __name__ == "__main__":
    raise SystemExit(main())
