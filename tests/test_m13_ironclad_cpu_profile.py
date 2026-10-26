# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Observer contracts only: synthetic calls provide no Docker timing evidence."""

import asyncio
import json
import subprocess
from types import SimpleNamespace

import pytest
from scripts.engineering.m13_ironclad_cpu_profile import NODE, execution_status, main, observe


@pytest.mark.asyncio
async def test_observer_preserves_values_arguments_and_redacts_commands(monkeypatch):
    calls = []
    result = subprocess.CompletedProcess([], 0, stdout="secret output")

    def original_run(*args, **kwargs):
        calls.append((args, kwargs))
        return result

    monkeypatch.setattr(subprocess, "run", original_run)
    outcome = SimpleNamespace(duration_seconds=4.2, timed_out=True, exit_code=-9)

    class Backend:
        docker_cmd = "/absolute/docker"

        def _remove_containers(self, targets, *, stable_seconds, wait_seconds):
            assert targets == ["secret-target"]
            assert stable_seconds == 3.0 and wait_seconds == 12.0
            assert (
                subprocess.run([self.docker_cmd, "inspect", "secret-target"], capture_output=True)
                is result
            )
            assert subprocess.run(["unrelated", "rm", "secret-other"]) is result

        async def execute(self, request):
            assert request is outcome
            await asyncio.to_thread(
                self._remove_containers, ["secret-target"], stable_seconds=3.0, wait_seconds=12.0
            )
            return outcome

    original_execute = Backend.execute
    original_cleanup = Backend._remove_containers
    records = {}
    with observe(Backend, records):
        assert await Backend().execute(outcome) is outcome
    assert Backend.execute is original_execute
    assert Backend._remove_containers is original_cleanup
    assert subprocess.run is original_run
    assert len(calls) == 2
    assert calls[0][1] == {"capture_output": True}
    assert len(records["docker_commands"]) == 1
    assert records["docker_commands"][0]["operation"] == "inspect"
    assert records["executions"][0]["outcome_duration_seconds"] == 4.2
    assert records["cleanups"][0]["stable_seconds"] == 3.0
    assert "secret" not in json.dumps(records)


@pytest.mark.asyncio
async def test_observer_preserves_cancellation_object_and_restores_methods():
    cancellation = asyncio.CancelledError()

    class Backend:
        docker_cmd = "docker"

        def _remove_containers(self, *args, **kwargs):
            raise cancellation

        async def execute(self, *args, **kwargs):
            self._remove_containers([], stable_seconds=3.0, wait_seconds=12.0)

    original_execute = Backend.execute
    original_cleanup = Backend._remove_containers
    original_run = subprocess.run
    records = {}
    with pytest.raises(asyncio.CancelledError) as caught:
        with observe(Backend, records):
            await Backend().execute()
    assert caught.value is cancellation
    assert Backend.execute is original_execute
    assert Backend._remove_containers is original_cleanup
    assert subprocess.run is original_run
    assert records["executions"][0]["exception_type"] == "CancelledError"
    assert records["cleanups"][0]["exception_type"] == "CancelledError"
    assert "outcome_duration_seconds" not in records["executions"][0]


@pytest.mark.asyncio
async def test_observer_preserves_docker_exception_without_message(monkeypatch):
    failure = subprocess.TimeoutExpired(["docker", "inspect", "secret-target"], 5)

    def original_run(*args, **kwargs):
        raise failure

    monkeypatch.setattr(subprocess, "run", original_run)

    class Backend:
        docker_cmd = "docker"

        def _remove_containers(self, *args, **kwargs):
            return None

        async def execute(self):
            subprocess.run(args=["docker", "inspect", "secret-target"], timeout=5)

    records = {}
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        with observe(Backend, records):
            await Backend().execute()
    assert caught.value is failure
    assert records["docker_commands"][0]["exception_type"] == "TimeoutExpired"
    assert "secret" not in json.dumps(records)


@pytest.mark.parametrize("arguments", [["--repetitions", "11"], ["--timeout", "181"]])
def test_observer_rejects_unbounded_runs(tmp_path, arguments):
    with pytest.raises(SystemExit) as caught:
        main(["--output", str(tmp_path), *arguments])
    assert caught.value.code == 2


def test_observer_never_reports_skips_or_missing_measurements_as_pass():
    assert execution_status({"pytest_reports": []}) == "NOT_EXECUTED"
    reports = [{"nodeid": NODE, "phase": "setup", "outcome": "skipped"}]
    assert execution_status({"pytest_reports": reports}) == "NOT_EXECUTED"
    reports = [{"nodeid": NODE, "phase": "call", "outcome": "passed"}]
    assert execution_status({"pytest_reports": reports}) == "INCOMPLETE_OBSERVATION"
    assert execution_status({"pytest_reports": reports, "executions": [{}]}) == "PASS"
    reports.append({"nodeid": NODE, "phase": "teardown", "outcome": "failed"})
    assert execution_status({"pytest_reports": reports, "executions": [{}]}) == "FAIL"


def test_observer_refuses_stale_output(tmp_path):
    (tmp_path / "run-1.json").write_text('{"status": "PASS"}')
    with pytest.raises(SystemExit) as caught:
        main(["--output", str(tmp_path)])
    assert caught.value.code == 2
