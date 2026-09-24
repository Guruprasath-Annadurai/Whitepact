# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Deterministic Alembic configuration resolution."""

from __future__ import annotations

import os
from pathlib import Path

WHITEPACT_ALEMBIC_INI_ENV = "WHITEPACT_ALEMBIC_INI"
RAI_ALEMBIC_INI_ENV = "RAI_ALEMBIC_INI"


class AlembicConfigError(Exception):
    """Raised when alembic.ini cannot be resolved or is invalid."""


def _env_override() -> Path | None:
    raw = os.environ.get(WHITEPACT_ALEMBIC_INI_ENV) or os.environ.get(RAI_ALEMBIC_INI_ENV)
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise AlembicConfigError(
            f"{WHITEPACT_ALEMBIC_INI_ENV} points to a missing file: {path}"
        )
    return path


def _package_known_ini() -> Path | None:
    """Wheel/sdist layout: alembic.ini shipped adjacent to the migrations package."""
    try:
        import responsibleai  # noqa: PLC0415

        pkg_root = Path(responsibleai.__file__).resolve().parent
    except Exception:
        return None
    for candidate in (
        pkg_root.parent / "alembic.ini",
        pkg_root / "alembic.ini",
    ):
        if candidate.is_file():
            return candidate
    return None


def _repository_known_ini() -> Path | None:
    """Editable install / git checkout: repo root above src/responsibleai."""
    here = Path(__file__).resolve()
    for base in (here.parents[3], here.parents[2], here.parents[1]):
        candidate = base / "alembic.ini"
        if candidate.is_file() and (base / "migrations").is_dir():
            return candidate
    return None


def _cwd_fallback_ini() -> Path | None:
    candidates = [Path.cwd()] + list(Path.cwd().parents)[:6]
    for base in candidates:
        candidate = base / "alembic.ini"
        if candidate.is_file():
            return candidate
    return None


def resolve_alembic_ini() -> Path:
    """Resolve alembic.ini using the canonical search order."""
    for resolver, label in (
        (_env_override, "environment override"),
        (_package_known_ini, "installed package path"),
        (_repository_known_ini, "repository path"),
        (_cwd_fallback_ini, "working directory"),
    ):
        try:
            path = resolver()
        except AlembicConfigError:
            raise
        if path is not None:
            return path
    raise AlembicConfigError(
        "Could not locate alembic.ini. Set WHITEPACT_ALEMBIC_INI to an existing "
        "configuration file, or run from a directory that contains alembic.ini."
    )
