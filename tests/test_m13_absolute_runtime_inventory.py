# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Read-only OCI discovery oracles. Fakes here do not prove native Docker behavior."""

import json
import subprocess

import pytest

from responsibleai.db.containment_repository import ContainmentAdmissionError
from responsibleai.isolation import durable_intent
from tests.test_m13_absolute_durable_intent import journal as journal


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entry",
    [
        {"ID": "c" * 64, "Names": "wp_iso_unknown", "Labels": ""},
        {"ID": "c" * 64, "Names": "foreign", "Labels": "io.whitepact.execution=unknown"},
    ],
)
async def test_unknown_work_fences_without_name_based_kill(journal, monkeypatch, entry):
    repository, _ = journal
    calls = []

    def inventory(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(entry), stderr="")

    monkeypatch.setattr(subprocess, "run", inventory)
    with pytest.raises(ContainmentAdmissionError):
        await durable_intent.assert_runtime_inventory(repository, "docker", "daemon")
    assert len(calls) == 1
    assert calls[0][1] == "ps"
    assert all("rm" not in command and "kill" not in command for command in calls)


@pytest.mark.asyncio
async def test_unmanaged_foreign_container_is_not_adopted_or_killed(journal, monkeypatch):
    repository, _ = journal
    commands = []

    def inventory(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"ID": "d" * 64, "Names": "foreign", "Labels": ""}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", inventory)
    await durable_intent.assert_runtime_inventory(repository, "docker", "daemon")
    assert len(commands) == 1 and commands[0][1] == "ps"


def test_required_journal_never_falls_back_in_production(monkeypatch):
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", "1")
    monkeypatch.setattr(
        durable_intent,
        "get_enterprise_engine",
        lambda: (_ for _ in ()).throw(RuntimeError("DB unavailable")),
    )
    with pytest.raises(RuntimeError, match="DB unavailable"):
        durable_intent.required_journal()


@pytest.mark.parametrize("stdout", ["", "../../forged", "a\nb", "x" * 129])
def test_invalid_daemon_identity_cannot_become_journal_owner(monkeypatch, stdout):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=stdout, stderr=""),
    )
    with pytest.raises(ContainmentAdmissionError):
        durable_intent.daemon_identity("docker")
