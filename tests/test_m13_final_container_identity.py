# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Detached recovery requires immutable CID plus matching Docker identity."""

import hashlib
import json
import subprocess

import pytest

from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.in_flight import verify_authoritative_container_containment

CID = "a" * 64


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["tenant", "execution", "cid", "name", None])
async def test_only_matching_immutable_identity_can_authorize_removal(monkeypatch, mismatch):
    obj = {
        "Id": CID,
        "Name": "/owned",
        "Config": {
            "Labels": {
                "io.whitepact.organization": hashlib.sha256(b"tenant").hexdigest(),
                "io.whitepact.execution": "execution",
            }
        },
    }
    if mismatch == "tenant":
        obj["Config"]["Labels"]["io.whitepact.organization"] = "foreign"
    elif mismatch == "execution":
        obj["Config"]["Labels"]["io.whitepact.execution"] = "old-execution"
    elif mismatch == "cid":
        obj["Id"] = "b" * 64
    elif mismatch == "name":
        obj["Name"] = "/reused-name"
    removed = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kw: subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps([obj]),
            stderr="",
        ),
    )
    monkeypatch.setattr(
        DockerContainerBackend,
        "_remove_containers",
        lambda self, targets, **kw: removed.extend(targets),
    )
    accepted = await verify_authoritative_container_containment(
        "owned",
        container_id=CID,
        organization_id="tenant",
        execution_id="execution",
    )
    assert accepted is (mismatch is None)
    assert removed == ([CID] if mismatch is None else [])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    ["authorization plugin not found", "No such object: x; plugin failed", "daemon unavailable"],
)
async def test_inspect_uncertainty_never_authorizes_removal(monkeypatch, error):
    calls = []

    def docker(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 1, stdout="", stderr=error)

    monkeypatch.setattr(subprocess, "run", docker)
    assert not await verify_authoritative_container_containment(
        "owned",
        container_id=CID,
        organization_id="tenant",
        execution_id="execution",
    )
    assert all(command[1] == "inspect" for command in calls)
