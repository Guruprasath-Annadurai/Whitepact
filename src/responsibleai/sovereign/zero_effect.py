# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Zero-effect operation markers — simulations must not invoke executors."""

from __future__ import annotations

import contextvars
import functools
import inspect
from collections.abc import Callable
from typing import Any, TypeVar

_ZERO_EFFECT: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "sovereign_zero_effect", default=False
)

F = TypeVar("F", bound=Callable[..., Any])


def is_zero_effect_context() -> bool:
    return _ZERO_EFFECT.get()


_consequential_invocation_count: contextvars.ContextVar[int] = contextvars.ContextVar(
    "sovereign_consequential_invocations", default=0
)


def record_consequential_invocation() -> None:
    if is_zero_effect_context():
        _consequential_invocation_count.set(_consequential_invocation_count.get() + 1)


def consequential_invocation_count() -> int:
    return _consequential_invocation_count.get()


def reset_consequential_invocation_count() -> None:
    _consequential_invocation_count.set(0)


def zero_effect_operation(fn: F) -> F:
    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            token = _ZERO_EFFECT.set(True)
            reset_consequential_invocation_count()
            try:
                return await fn(*args, **kwargs)
            finally:
                _ZERO_EFFECT.reset(token)

        return async_wrapper  # type: ignore[return-value]

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        token = _ZERO_EFFECT.set(True)
        reset_consequential_invocation_count()
        try:
            return fn(*args, **kwargs)
        finally:
            _ZERO_EFFECT.reset(token)

    return wrapper  # type: ignore[return-value]


class ZeroEffectScope:
    def __enter__(self) -> ZeroEffectScope:
        self._token = _ZERO_EFFECT.set(True)
        reset_consequential_invocation_count()
        return self

    def __exit__(self, *exc: object) -> None:
        _ZERO_EFFECT.reset(self._token)
