# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Stage 19 Linux execution qualification. TEST_ONLY. Not customer identity."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from scripts.engineering.m13_stage19_host_qualification import (
    probe_host,
    require_qualification_host,
)
from sqlalchemy import text

from responsibleai.enterprise.runtime import configure_enterprise
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.filesystem import EphemeralWorkspace
from responsibleai.isolation.models import IsolatedExecutionRequest, IsolationProfile
from tests.docker_runtime import enable_containment_probe
from tests.protected_component_tenant import (
    component_controller,
    provision_component_organization,
)

RUNNER = """
import json, socket
network = "open"
try:
    sock = socket.socket()
    sock.settimeout(1)
    sock.connect(("1.1.1.1", 443))
except Exception:
    network = "denied"
print(json.dumps({"status": "success", "result": {"marker": "TEST_ONLY", "network": network}}))
"""


def test_host_probe_records_real_capabilities(monkeypatch):
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    evidence = probe_host()
    require_qualification_host(evidence)
    assert evidence["production_certified"] is False
    assert evidence["docker_daemon_id"]


def test_posix_acl_grants_container_uid_and_can_be_removed(tmp_path):
    with EphemeralWorkspace("stage19", "acl") as workspace:
        workspace.populate({"note.txt": "TEST_ONLY"})
        workspace.prepare_for_container()
        listed = subprocess.run(
            ["getfacl", "-p", str(workspace.path / "note.txt")],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "user:nobody:r--" in listed.stdout
        mode = os.stat(workspace.path / "note.txt").st_mode
        assert mode & 0o007 == 0
    assert not (tmp_path / "note.txt").exists()


@pytest.mark.asyncio
async def test_postgres_journaled_container_denies_network(tmp_path, monkeypatch):
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    evidence = probe_host()
    require_qualification_host(evidence)
    enable_containment_probe(monkeypatch)
    async with component_controller(tmp_path, monkeypatch, "s19") as controller:
        engine = controller.engine
        configure_enterprise(engine)
        org = await provision_component_organization(
            engine, name="Stage 19 test", slug=f"s19-{uuid.uuid4().hex[:8]}"
        )
        async with engine.raw.connect() as connection:
            version = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            status = await connection.scalar(
                text("SELECT governance_status FROM organizations WHERE id=:id"),
                {"id": org.id},
            )
        assert version == "0067"
        assert status == "ACTIVE"
        outcome = await DockerContainerBackend().execute(
            IsolatedExecutionRequest(
                action_id="stage19",
                organization_id=org.id,
                action_type="test.harmless",
                arguments={"marker": "TEST_ONLY"},
                profile=IsolationProfile(),
                workspace_files={"runner.py": RUNNER},
                authorization_id=uuid.uuid4().hex,
                action_digest="ab" * 32,
                authorization_expires_at=datetime.now(UTC) + timedelta(minutes=5),
                admission_epoch=1,
            )
        )
        assert outcome.is_success
        assert outcome.result_payload == {"marker": "TEST_ONLY", "network": "denied"}
        async with engine.raw.connect() as connection:
            states = (
                (await connection.execute(text("SELECT state FROM runtime_containment_records")))
                .scalars()
                .all()
            )
        assert states == ["CONTAINED"]


def test_evidence_file_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    monkeypatch.setenv("WHITEPACT_STAGE19_EVIDENCE", str(tmp_path / "host.json"))
    env = os.environ.copy()
    env.pop("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", None)
    subprocess.run(
        [sys.executable, "scripts/engineering/m13_stage19_host_qualification.py"],
        check=True,
        cwd=os.environ.get("WHITEPACT_STAGE19_ROOT", "."),
        env=env,
    )
    payload = json.loads((tmp_path / "host.json").read_text(encoding="utf-8"))
    assert payload["format"] == "WHITEPACT-M13-STAGE19-HOST-PROBE-V1"
    assert payload["production_certified"] is False
