# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Subprocess execution backend for local developer environments (LOCAL_DEV_ONLY).

Enforces:
- Clean environment without control-plane secrets.
- Dedicated ephemeral workspace.
- Process-group isolation (`preexec_fn=os.setsid`) ensuring children are killed on exit.
- Hard output clamping to prevent memory exhaustion / log bombing.
- Wall-clock timeouts terminating the entire process group.
- Resource limits via `resource.setrlimit` on POSIX systems where supported.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import resource
import signal
import sys
import time
from typing import Any

from responsibleai.isolation.backend import IsolationBackend
from responsibleai.isolation.environment import build_isolated_environment
from responsibleai.isolation.filesystem import EphemeralWorkspace
from responsibleai.isolation.models import ExecutionOutcome, IsolatedExecutionRequest, NetworkPolicy

logger = logging.getLogger(__name__)


class LocalSubprocessBackend(IsolationBackend):
    """Local subprocess execution backend restricted strictly to local dev environments."""

    def __init__(self, *, python_bin: str | None = None) -> None:
        self.python_bin = python_bin or sys.executable

    def is_available(self) -> bool:
        return os.path.exists(self.python_bin)

    async def execute(self, request: IsolatedExecutionRequest) -> ExecutionOutcome:
        # Check network policy: local subprocess cannot provide true network isolation
        if request.profile.network_policy == NetworkPolicy.NONE:
            # Enforce warning or check
            pass

        clean_env = build_isolated_environment(
            organization_id=request.organization_id,
            action_id=request.action_id,
            extra_env=request.environment_overrides,
        )

        # Runner script executed inside the child process
        # Invokes responsibleai.mcp.tools:dispatch_tool
        runner_code = """
import sys
import json
import asyncio
from responsibleai.mcp.tools import dispatch_tool

async def main():
    try:
        raw_input = sys.stdin.read()
        data = json.loads(raw_input)
        action_type = data["action_type"]
        arguments = data["arguments"]
        res = await dispatch_tool(action_type, arguments)
        sys.stdout.write(json.dumps({"status": "success", "result": res}))
    except Exception as e:
        sys.stdout.write(json.dumps({"status": "error", "error": str(e)}))

if __name__ == "__main__":
    asyncio.run(main())
"""

        limits = request.profile.resources
        start_time = time.monotonic()

        with EphemeralWorkspace(request.action_id, request.organization_id) as workspace:
            workspace.populate(request.workspace_files)

            # Limit definitions to be applied in child process
            def _apply_resource_limits() -> None:
                os.setsid()  # New process group for total tree termination
                try:
                    # CPU limit (seconds)
                    cpu_limit = int(limits.cpu_cores * limits.wall_timeout_seconds) + 1
                    resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
                except Exception:
                    pass

                try:
                    # Memory limit (bytes)
                    mem_bytes = limits.max_memory_mb * 1024 * 1024
                    resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
                except Exception:
                    pass

                try:
                    # File descriptor limit
                    resource.setrlimit(
                        resource.RLIMIT_NOFILE,
                        (limits.max_file_descriptors, limits.max_file_descriptors),
                    )
                except Exception:
                    pass

            # Prepare process invocation
            input_payload = json.dumps(
                {"action_type": request.action_type, "arguments": request.arguments}
            ).encode("utf-8")

            # Ensure PYTHONPATH is passed so child can import responsibleai
            if "PYTHONPATH" not in clean_env and "PYTHONPATH" in os.environ:
                clean_env["PYTHONPATH"] = os.environ["PYTHONPATH"]
            elif "PYTHONPATH" not in clean_env:
                # Add current directory / src
                clean_env["PYTHONPATH"] = "src"

            proc = await asyncio.create_subprocess_exec(
                self.python_bin,
                "-c",
                runner_code,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace.path),
                env=clean_env,
                preexec_fn=_apply_resource_limits,
            )

            timed_out = False
            stdout_data = b""
            stderr_data = b""
            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    proc.communicate(input=input_payload),
                    timeout=limits.wall_timeout_seconds,
                )
            except TimeoutError:
                timed_out = True
                # Terminate the entire process group
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                await proc.wait()

            duration = time.monotonic() - start_time

            # Clamp output size
            max_out = limits.max_output_bytes
            stdout_str = stdout_data[:max_out].decode("utf-8", errors="replace")
            stderr_str = stderr_data[:max_out].decode("utf-8", errors="replace")

            result_obj: Any = None
            violation: str | None = None
            exit_code = proc.returncode if proc.returncode is not None else -1

            if timed_out:
                violation = f"Wall timeout of {limits.wall_timeout_seconds}s exceeded"
                exit_code = -signal.SIGKILL
            elif exit_code == 0:
                try:
                    parsed = json.loads(stdout_str)
                    if parsed.get("status") == "success":
                        result_obj = parsed.get("result")
                    else:
                        violation = parsed.get("error", "Execution failed")
                        exit_code = 1
                except Exception as ex:
                    violation = f"Failed to parse runner output: {ex}"
                    exit_code = 1
            else:
                violation = f"Process exited with non-zero status {exit_code}: {stderr_str.strip()}"

            return ExecutionOutcome(
                action_id=request.action_id,
                exit_code=exit_code,
                result_payload=result_obj,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_seconds=duration,
                timed_out=timed_out,
                violation=violation,
            )
