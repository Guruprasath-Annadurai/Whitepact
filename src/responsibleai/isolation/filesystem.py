# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Ephemeral workspace lifecycle manager with traversal defense."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path

from responsibleai.isolation.errors import FilesystemEscapeError


class EphemeralWorkspace:
    """Manages an isolated temporary workspace directory for a single execution."""

    def __init__(self, action_id: str, organization_id: str) -> None:
        self.action_id = action_id
        self.organization_id = organization_id
        self._temp_dir: str | None = None
        self._path: Path | None = None

    def __enter__(self) -> EphemeralWorkspace:
        self._temp_dir = tempfile.mkdtemp(prefix=f"wp_{self.organization_id}_{self.action_id}_")
        self._path = Path(self._temp_dir).resolve()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup()

    @property
    def path(self) -> Path:
        if self._path is None:
            raise RuntimeError("Workspace has not been entered.")
        return self._path

    def populate(self, files: Mapping[str, str | bytes]) -> None:
        """Safely write files into the workspace, preventing directory traversal."""
        root = self.path
        for rel_path, content in files.items():
            # Validate path does not escape workspace root
            target = (root / rel_path).resolve()
            if not str(target).startswith(str(root)):
                raise FilesystemEscapeError(
                    f"Path '{rel_path}' attempts traversal outside workspace root."
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, str):
                target.write_text(content, encoding="utf-8")
            else:
                target.write_bytes(content)

    def make_world_readable(self) -> None:
        """Allow an unprivileged container UID to read workspace files.

        Directories are 0755 and files 0644. The mount stays host-owned; the
        container user cannot rewrite the tree.
        """
        root = self.path
        os.chmod(root, 0o755)
        for dirpath, dirnames, filenames in os.walk(root):
            os.chmod(dirpath, 0o755)
            for name in filenames:
                os.chmod(os.path.join(dirpath, name), 0o644)

    def cleanup(self) -> None:
        """Purge all workspace contents from disk."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except Exception:
                pass
        self._temp_dir = None
        self._path = None
