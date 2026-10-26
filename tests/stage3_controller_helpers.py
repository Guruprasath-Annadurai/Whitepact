# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Disposable, separately running controller with private test-only credentials."""

import asyncio
import base64
import json
import os
import stat
import subprocess
import sys
import tempfile
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat


@asynccontextmanager
async def controller_process(service, monkeypatch):
    with tempfile.TemporaryDirectory(
        prefix="wp-stage3-", dir="/private/tmp" if sys.platform == "darwin" else "/tmp"
    ) as directory:
        root = Path(directory)
        socket_path = root / "controller.sock"
        profile = root / "private.json"
        trust = asdict(service.trust) | {"public_key": service.trust.public_key.hex()}
        config = {
            "purpose": "NONPRODUCTION_PROVISIONING_QUALIFICATION",
            "socket_path": str(socket_path),
            "database_url": service.engine.raw.url.render_as_string(hide_password=False),
            "store_b_path": str(service.provider.path),
            "store_b_key": service.provider._secret_key,
            "trust": trust,
            "private_key": base64.b64encode(
                service.key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
            ).decode("ascii"),
        }
        descriptor = os.open(profile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(config, stream)
        child = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "responsibleai.data_governance.tenant_controller_server",
                "--config",
                str(profile),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            async with asyncio.timeout(20):
                while not socket_path.exists():
                    if child.poll() is not None:
                        raise RuntimeError(
                            f"Disposable controller exited with code {child.returncode}; no credentials logged"
                        )
                    await asyncio.sleep(0.05)
            monkeypatch.setenv("WHITEPACT_TENANT_CONTROLLER_SOCKET", str(socket_path))
            monkeypatch.setenv("WHITEPACT_TENANT_CONTROLLER_UID", str(os.getuid()))
            assert stat.S_IMODE(socket_path.lstat().st_mode) == 0o660
            yield child
        finally:
            child.terminate()
            try:
                await asyncio.to_thread(child.wait, 10)
            except subprocess.TimeoutExpired:
                child.kill()
                await asyncio.to_thread(child.wait, 5)
