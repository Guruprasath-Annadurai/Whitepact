# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Observe the unchanged Docker CPU regression; never alter its assertions.

Each repetition uses a fresh pytest process. Host process/thread CPU measurements
exclude Docker CLI, daemon and container CPU. Observer tests are instrumentation
contracts, not Docker performance evidence.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

NODE = (
    "tests/test_runtime_isolation_stress.py::"
    "TestProductionContainerResourceAttacks::test_cpu_busy_loop_bounded"
)


def provenance() -> dict[str, str]:
    result = {}
    for key, arguments in {
        "head": ["rev-parse", "HEAD"],
        "tree": ["rev-parse", "HEAD^{tree}"],
        "parent": ["rev-parse", "HEAD^"],
        "git_status": ["status", "--porcelain=v1"],
    }.items():
        result[key] = subprocess.check_output(["git", *arguments], text=True).strip()
    return result


@contextmanager
def observe(backend_class: type, records: dict[str, Any]):
    """Temporarily wrap calls, preserving return values, exceptions and awaits.

    No clock, sleep, timeout, cancellation, subprocess result, or runtime input is
    replaced. Docker command arguments/output are deliberately not recorded.
    Process CPU intervals overlap and must not be summed across observations.
    """
    original_execute = backend_class.execute
    original_cleanup = backend_class._remove_containers
    original_run = subprocess.run
    docker_commands: set[str] = set()
    lock = threading.Lock()
    records.update(executions=[], cleanups=[], docker_commands=[])

    @functools.wraps(original_execute)
    async def execute(self, *args, **kwargs):
        with lock:
            docker_commands.add(os.fspath(self.docker_cmd))
        started = time.perf_counter()
        cpu = time.process_time()
        thread_cpu = time.thread_time()
        row: dict[str, Any] = {}
        try:
            outcome = await original_execute(self, *args, **kwargs)
            row.update(
                outcome_duration_seconds=outcome.duration_seconds,
                timed_out=outcome.timed_out,
                exit_code=outcome.exit_code,
            )
            return outcome
        except BaseException as exc:
            row["exception_type"] = type(exc).__name__
            raise
        finally:
            row.update(
                wall_seconds=time.perf_counter() - started,
                host_process_cpu_seconds=time.process_time() - cpu,
                host_thread_cpu_seconds=time.thread_time() - thread_cpu,
            )
            with lock:
                records["executions"].append(row)

    @functools.wraps(original_cleanup)
    def cleanup(self, *args, **kwargs):
        started = time.perf_counter()
        cpu = time.process_time()
        thread_cpu = time.thread_time()
        row: dict[str, Any] = {
            "stable_seconds": kwargs.get("stable_seconds"),
            "wait_seconds": kwargs.get("wait_seconds"),
        }
        try:
            return original_cleanup(self, *args, **kwargs)
        except BaseException as exc:
            row["exception_type"] = type(exc).__name__
            raise
        finally:
            row.update(
                wall_seconds=time.perf_counter() - started,
                host_process_cpu_seconds=time.process_time() - cpu,
                host_thread_cpu_seconds=time.thread_time() - thread_cpu,
            )
            with lock:
                records["cleanups"].append(row)

    @functools.wraps(original_run)
    def run(*args, **kwargs):
        command = args[0] if args else kwargs.get("args")
        with lock:
            selected = (
                isinstance(command, (list, tuple))
                and len(command) > 1
                and os.fspath(command[0]) in docker_commands
                and command[1] in {"rm", "inspect"}
            )
        if not selected:
            return original_run(*args, **kwargs)
        started = time.perf_counter()
        cpu = time.process_time()
        thread_cpu = time.thread_time()
        row: dict[str, Any] = {"operation": command[1]}
        try:
            result = original_run(*args, **kwargs)
            row["returncode"] = result.returncode
            return result
        except BaseException as exc:
            row["exception_type"] = type(exc).__name__
            raise
        finally:
            row.update(
                wall_seconds=time.perf_counter() - started,
                host_process_cpu_seconds=time.process_time() - cpu,
                host_thread_cpu_seconds=time.thread_time() - thread_cpu,
            )
            with lock:
                records["docker_commands"].append(row)

    backend_class.execute = execute
    backend_class._remove_containers = cleanup
    subprocess.run = run
    try:
        yield
    finally:
        subprocess.run = original_run
        backend_class._remove_containers = original_cleanup
        backend_class.execute = original_execute


class Reports:
    def __init__(self):
        self.rows: list[dict[str, Any]] = []

    def pytest_runtest_logreport(self, report):
        self.rows.append({"nodeid": report.nodeid, "phase": report.when, "outcome": report.outcome})


def execution_status(records: dict[str, Any]) -> str:
    reports = records.get("pytest_reports", [])
    if any(row["outcome"] == "failed" for row in reports):
        return "FAIL"
    calls = [row for row in reports if row["nodeid"] == NODE and row["phase"] == "call"]
    if len(calls) != 1 or calls[0]["outcome"] != "passed":
        return "NOT_EXECUTED"
    if len(records.get("executions", [])) != 1:
        return "INCOMPLETE_OBSERVATION"
    return "PASS"


def worker(output: Path, pytest_arguments: list[str]) -> int:
    import pytest

    from responsibleai.isolation.container_backend import DockerContainerBackend

    records: dict[str, Any] = {
        "provenance": provenance(),
        "python": sys.version,
        "node": NODE,
        "cpu_scope": "Python host process/thread only; excludes Docker CLI, daemon and container CPU",
        "timing_note": "nested/overlapping intervals are not additive; instrumentation adds overhead",
    }
    reports = Reports()
    started = time.perf_counter()
    cpu = time.process_time()
    thread_cpu = time.thread_time()
    try:
        with observe(DockerContainerBackend, records):
            code = int(pytest.main([NODE, *pytest_arguments], plugins=[reports]))
        records["pytest_exit_code"] = code
        return code
    finally:
        records.update(
            wall_seconds=time.perf_counter() - started,
            host_process_cpu_seconds=time.process_time() - cpu,
            host_thread_cpu_seconds=time.thread_time() - thread_cpu,
            pytest_reports=reports.rows,
        )
        records["status"] = execution_status(records)
        records["docker_command_counts"] = {
            operation: sum(
                row["operation"] == operation for row in records.get("docker_commands", [])
            )
            for operation in ("rm", "inspect")
        }
        output.write_text(json.dumps(records, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("pytest_arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if not 1 <= args.repetitions <= 10 or not 1 <= args.timeout <= 180:
        parser.error("repetitions must be 1..10 and per-process timeout 1..180 seconds")
    forwarded = args.pytest_arguments
    if forwarded[:1] == ["--"]:
        forwarded = forwarded[1:]
    if args.worker:
        return worker(args.output, forwarded)
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        parser.error("output directory must be empty; refusing stale evidence reuse")
    summary: dict[str, Any] = {"provenance": provenance(), "node": NODE, "runs": []}
    failed = False
    for index in range(args.repetitions):
        receipt = args.output / f"run-{index + 1}.json"
        log = args.output / f"run-{index + 1}.log"
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--output",
            str(receipt),
            "--",
            *forwarded,
        ]
        row: dict[str, Any] = {"index": index + 1, "receipt": receipt.name, "log": log.name}
        started = time.perf_counter()
        try:
            with log.open("w") as stream:
                result = subprocess.run(
                    command,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    timeout=args.timeout,
                    check=False,
                )
            row["returncode"] = result.returncode
            failed |= result.returncode != 0
        except subprocess.TimeoutExpired:
            row["status"] = "TIMEOUT"
            failed = True
        row["wall_seconds"] = time.perf_counter() - started
        row["receipt_exists"] = receipt.is_file()
        failed |= not receipt.is_file()
        if receipt.is_file():
            try:
                observed = json.loads(receipt.read_text())
                row["status"] = observed["status"]
                row["provenance_matches"] = observed["provenance"] == summary["provenance"]
                failed |= row["status"] != "PASS" or not row["provenance_matches"]
            except (ValueError, KeyError, TypeError):
                row["status"] = "INVALID_RECEIPT"
                failed = True
        summary["runs"].append(row)
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
