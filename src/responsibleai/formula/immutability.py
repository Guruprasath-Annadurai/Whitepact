# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def _freeze_sort_key(value: Any) -> str:
    """Deterministic sort key for unordered collections."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return freeze_mapping(value)
    if isinstance(value, (set, frozenset)):
        frozen_items = [freeze_value(v) for v in value]
        return tuple(sorted(frozen_items, key=_freeze_sort_key))
    if isinstance(value, list):
        return tuple(freeze_value(v) for v in value)
    if isinstance(value, tuple):
        return tuple(freeze_value(v) for v in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"non-canonical value type in formula snapshot: {type(value)!r}")


def freeze_mapping(mapping: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted((str(k), freeze_value(v)) for k, v in mapping.items()))
