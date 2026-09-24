# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
from pathlib import Path

import pytest

from responsibleai.db.alembic_paths import AlembicConfigError, resolve_alembic_ini

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_resolve_from_repository_root() -> None:
    path = resolve_alembic_ini()
    assert path.is_file()
    assert path.name == "alembic.ini"
    assert (path.parent / "migrations").is_dir()


def test_env_override_must_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "missing.ini"
    monkeypatch.setenv("WHITEPACT_ALEMBIC_INI", str(missing))
    with pytest.raises(AlembicConfigError, match="missing file"):
        resolve_alembic_ini()


def test_env_override_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ini = tmp_path / "alembic.ini"
    ini.write_text("[alembic]\nscript_location = migrations\n", encoding="utf-8")
    monkeypatch.setenv("WHITEPACT_ALEMBIC_INI", str(ini))
    assert resolve_alembic_ini() == ini.resolve()


def test_resolve_from_nested_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    nested = REPO_ROOT / "src" / "responsibleai"
    monkeypatch.delenv("WHITEPACT_ALEMBIC_INI", raising=False)
    monkeypatch.chdir(nested)
    path = resolve_alembic_ini()
    assert path == (REPO_ROOT / "alembic.ini").resolve()


def test_resolve_from_tmp_without_override_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("WHITEPACT_ALEMBIC_INI", raising=False)
    monkeypatch.setattr(
        "responsibleai.db.alembic_paths._package_known_ini", lambda: None
    )
    monkeypatch.setattr(
        "responsibleai.db.alembic_paths._repository_known_ini", lambda: None
    )
    monkeypatch.chdir(tmp_path)
    with pytest.raises(AlembicConfigError):
        resolve_alembic_ini()
