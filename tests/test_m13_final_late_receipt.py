# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Late Docker acknowledgment may be recovered only from a private receipt."""

import hashlib
import json
import subprocess

import pytest

from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.in_flight import verify_authoritative_container_containment


@pytest.mark.asyncio
@pytest.mark.parametrize("private", [True, False])
async def test_late_acknowledgment_requires_private_file_and_daemon_identity(
    monkeypatch, tmp_path, private
):
    receipt_dir = tmp_path / "receipt"
    receipt_dir.mkdir(mode=0o700 if private else 0o755)
    receipt = receipt_dir / "container.cid"
    cid = "c" * 64
    receipt.write_text(cid, encoding="ascii")
    removed = []
    inspected = []

    def docker(command, **kwargs):
        inspected.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stderr="",
            stdout=json.dumps(
                [
                    {
                        "Id": cid,
                        "Name": "/owned",
                        "Config": {
                            "Labels": {
                                "io.whitepact.organization": hashlib.sha256(b"tenant").hexdigest(),
                                "io.whitepact.execution": "execution",
                            }
                        },
                    }
                ]
            ),
        )

    monkeypatch.setattr(subprocess, "run", docker)
    monkeypatch.setattr(
        DockerContainerBackend,
        "_remove_containers",
        lambda self, targets, **kw: removed.extend(targets),
    )
    accepted = await verify_authoritative_container_containment(
        "owned",
        organization_id="tenant",
        execution_id="execution",
        container_receipt=str(receipt),
    )
    assert accepted is private
    assert removed == ([cid] if private else [])
    if not private:
        assert inspected == []
