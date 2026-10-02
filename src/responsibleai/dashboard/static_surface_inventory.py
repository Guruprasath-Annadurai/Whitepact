# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Deterministic classification of dashboard static tree (M2 / BLK-P0-06)."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from responsibleai.dashboard.legacy_frontend import (
    UNIFIED_SAAS_STATIC_ALLOW_PREFIXES,
    UNIFIED_SAAS_STATIC_ALLOW_REL_PATHS,
)

_STATIC_ROOT = Path(__file__).resolve().parent / "static"


class StaticAssetClass(StrEnum):
    MODERN_WHITEPACT = "modern_whitepact"
    PUBLIC_SHARED = "public_shared"
    UNKNOWN = "unknown"


def classify_static_relpath(relpath: str) -> StaticAssetClass:
    normalized = relpath.replace("\\", "/").lstrip("/")
    if any(normalized.startswith(prefix) for prefix in UNIFIED_SAAS_STATIC_ALLOW_PREFIXES):
        return StaticAssetClass.MODERN_WHITEPACT
    if normalized in UNIFIED_SAAS_STATIC_ALLOW_REL_PATHS:
        return StaticAssetClass.PUBLIC_SHARED
    return StaticAssetClass.UNKNOWN


def iter_static_files() -> list[tuple[str, StaticAssetClass]]:
    if not _STATIC_ROOT.is_dir():
        return []
    out: list[tuple[str, StaticAssetClass]] = []
    for path in sorted(_STATIC_ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(_STATIC_ROOT).as_posix()
        out.append((rel, classify_static_relpath(rel)))
    return out


def unknown_static_files() -> list[str]:
    return [rel for rel, cls in iter_static_files() if cls is StaticAssetClass.UNKNOWN]
