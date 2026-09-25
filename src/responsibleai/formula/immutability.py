# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return freeze_mapping(value)
    if isinstance(value, (list, set)):
        return tuple(freeze_value(v) for v in value)
    if isinstance(value, tuple):
        return tuple(freeze_value(v) for v in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"non-canonical value type in formula snapshot: {type(value)!r}")


def freeze_mapping(mapping: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted((str(k), freeze_value(v)) for k, v in mapping.items()))
