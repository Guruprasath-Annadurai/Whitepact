# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations


def compose_persistence(*values: bool) -> bool:
    """Conservative merge: persistent if any support path asserts persistence."""
    return any(values)
