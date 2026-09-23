# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Ephemeral workspace lifecycle manager with traversal defense."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path

from responsibleai.isolation.errors import FilesystemEscapeError, IsolationFilesystemPermissionError

# Container isolation runs as nobody:nogroup. Host trees stay owner-only.
DEFAULT_CONTAINER_UID = 65534
DEFAULT_CONTAINER_GID = 65534

_DIR_MODE = 0o700
_FILE_MODE = 0o600


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
        os.chmod(self._temp_dir, _DIR_MODE)
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
            os.chmod(target.parent, _DIR_MODE)
            if isinstance(content, str):
                target.write_text(content, encoding="utf-8")
            else:
                target.write_bytes(content)
            os.chmod(target, _FILE_MODE)

    def prepare_for_container(
        self,
        *,
        uid: int = DEFAULT_CONTAINER_UID,
        gid: int = DEFAULT_CONTAINER_GID,
    ) -> None:
        """Least-privilege host tree plus a narrowly scoped container mapping.

        Host enclosing workspace is ``0700`` / files ``0600`` (never world
        readable). The unprivileged container UID is granted access via POSIX
        ACL when available, otherwise by ``chown`` when the host process is
        root. Sticky world-writable directory modes are forbidden.
        Fail closed if the container UID cannot be granted access without
        exposing the tree to unrelated host users.
        """
        root = self.path
        self._chmod_owner_only(root)
        if _try_setfacl(root, uid=uid):
            return
        if os.geteuid() == 0:
            _chown_tree(root, uid=uid, gid=gid)
            self._chmod_owner_only(root)
            return
        raise IsolationFilesystemPermissionError(
            "Cannot grant the unprivileged container UID access to the "
            "execution workspace without world-readable permissions. "
            "Install POSIX ACLs (setfacl) or run the isolation host as root "
            "so the tree can be chowned to the container UID. Refusing a world-readable fallback."
        )

    def _chmod_owner_only(self, root: Path) -> None:
        os.chmod(root, _DIR_MODE)
        for dirpath, dirnames, filenames in os.walk(root):
            os.chmod(dirpath, _DIR_MODE)
            for name in dirnames:
                os.chmod(os.path.join(dirpath, name), _DIR_MODE)
            for name in filenames:
                os.chmod(os.path.join(dirpath, name), _FILE_MODE)

    def cleanup(self) -> None:
        """Purge all workspace contents from disk."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except Exception:
                pass
        self._temp_dir = None
        self._path = None


def workspace_is_world_accessible(path: Path) -> bool:
    """True if any path component is readable or writable by other users."""
    for dirpath, dirnames, filenames in os.walk(path):
        if _mode_has_other(os.stat(dirpath).st_mode):
            return True
        for name in dirnames:
            if _mode_has_other(os.stat(os.path.join(dirpath, name)).st_mode):
                return True
        for name in filenames:
            if _mode_has_other(os.stat(os.path.join(dirpath, name)).st_mode):
                return True
    return _mode_has_other(os.stat(path).st_mode)


def _mode_has_other(mode: int) -> bool:
    return bool(mode & (stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH))


def _try_setfacl(root: Path, *, uid: int) -> bool:
    setfacl = shutil.which("setfacl")
    if setfacl is None:
        return False
    dir_acl = f"u:{uid}:rwx"
    file_acl = f"u:{uid}:r"
    try:
        subprocess.run(  # noqa: S603
            [setfacl, "-m", dir_acl, str(root)],
            check=True,
            capture_output=True,
            timeout=10,
        )
        subprocess.run(  # noqa: S603
            [setfacl, "-d", "-m", dir_acl, str(root)],
            check=True,
            capture_output=True,
            timeout=10,
        )
        for dirpath, dirnames, filenames in os.walk(root):
            subprocess.run(  # noqa: S603
                [setfacl, "-m", dir_acl, dirpath],
                check=True,
                capture_output=True,
                timeout=10,
            )
            subprocess.run(  # noqa: S603
                [setfacl, "-d", "-m", dir_acl, dirpath],
                check=True,
                capture_output=True,
                timeout=10,
            )
            for name in dirnames:
                subprocess.run(  # noqa: S603
                    [setfacl, "-m", dir_acl, os.path.join(dirpath, name)],
                    check=True,
                    capture_output=True,
                    timeout=10,
                )
            for name in filenames:
                subprocess.run(  # noqa: S603
                    [setfacl, "-m", file_acl, os.path.join(dirpath, name)],
                    check=True,
                    capture_output=True,
                    timeout=10,
                )
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
        return False
    return True


def _chown_tree(root: Path, *, uid: int, gid: int) -> None:
    os.chown(root, uid, gid)
    for dirpath, dirnames, filenames in os.walk(root):
        os.chown(dirpath, uid, gid)
        for name in dirnames:
            os.chown(os.path.join(dirpath, name), uid, gid)
        for name in filenames:
            os.chown(os.path.join(dirpath, name), uid, gid)
