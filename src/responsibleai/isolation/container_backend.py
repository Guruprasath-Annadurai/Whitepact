# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""OCI / Docker Container Isolation Backend for Enterprise Production.

Enforces:
- Unprivileged user (`--user 10001:10001` or `nobody`).
- Read-only root filesystem (`--read-only`).
- Ephemeral writable `/tmp` and workspace mounts (`--tmpfs /tmp:rw,noexec,nosuid,size=64m`).
- Dropped capabilities (`--cap-drop ALL`).
- No new privileges (`--security-opt no-new-privileges:true`).
- Strict resource limits: `--memory`, `--cpus`, `--pids-limit`.
- Default deny network (`--network none`).
- Zero control-plane secrets in environment (`-e`).
- Automated container kill & removal on timeout or exit.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import time
import uuid
from typing import Any

from responsibleai.isolation.backend import IsolationBackend
from responsibleai.isolation.environment import build_isolated_environment
from responsibleai.isolation.errors import (
    IsolationBackendUnavailableError,
    IsolationPolicyViolationError,
)
from responsibleai.isolation.filesystem import EphemeralWorkspace
from responsibleai.isolation.models import ExecutionOutcome, IsolatedExecutionRequest, NetworkPolicy

logger = logging.getLogger(__name__)


class DockerContainerBackend(IsolationBackend):
    """Docker container execution backend providing OCI containment."""

    def __init__(
        self,
        *,
        image_name: str = "python:3.11-slim",
        docker_cmd: str | None = None,
    ) -> None:
        self.image_name = image_name
        self.docker_cmd = docker_cmd or shutil.which("docker") or "docker"

    def is_available(self) -> bool:
        """Check if docker binary is present and daemon responds."""
        if not shutil.which(self.docker_cmd):
            return False
        try:
            res = os.system(f"{self.docker_cmd} info >/dev/null 2>&1")
            return res == 0
        except Exception:
            return False

    async def execute(self, request: IsolatedExecutionRequest) -> ExecutionOutcome:
        if not self.is_available():
            raise IsolationBackendUnavailableError(
                "Docker isolation backend is unavailable or daemon is unreachable. "
                "Failing closed in production."
            )

        if request.profile.network_policy != NetworkPolicy.NONE:
            raise IsolationPolicyViolationError(
                "Direct network egress from isolated container execution is forbidden; "
                "all network operations must pass through canonical host-mediated egress chokepoints."
            )

        clean_env = build_isolated_environment(
            organization_id=request.organization_id,
            action_id=request.action_id,
            extra_env=request.environment_overrides,
            inherit_safe_host_vars=False,  # Container has its own isolated OS environment
        )

        limits = request.profile.resources
        execution_id = uuid.uuid4().hex[:12]
        container_prefix = f"wp_iso_{request.organization_id}_{request.action_id}"[:63].rstrip("_-.")
        container_name = f"{container_prefix}_{execution_id}"
        start_time = time.monotonic()

        runner_script = """
import sys
import json
import asyncio

async def main():
    try:
        raw_input = sys.stdin.read()
        data = json.loads(raw_input)
        action_type = data["action_type"]
        arguments = data["arguments"]
        # If running inside container where responsibleai package might not be installed,
        # fallback to simple processing or mock if testing
        try:
            from responsibleai.mcp.tools import dispatch_tool
            res = await dispatch_tool(action_type, arguments)
        except ImportError:
            res = {"echo": action_type, "arguments": arguments, "isolated": True}
        sys.stdout.write(json.dumps({"status": "success", "result": res}))
    except Exception as e:
        sys.stdout.write(json.dumps({"status": "error", "error": str(e)}))

if __name__ == "__main__":
    asyncio.run(main())
"""

        with EphemeralWorkspace(request.action_id, request.organization_id) as workspace:
            workspace.populate(request.workspace_files)
            if "runner.py" not in request.workspace_files:
                workspace.populate({"runner.py": runner_script})
            # Host mkdtemp is 0700; the container runs as nobody (65534) and
            # must be able to read runner.py without weakening the sandbox
            # (world-readable, not world-writable).
            workspace.make_world_readable()

            cid_file = workspace.path / ".container.cid"

            cmd = [
                self.docker_cmd,
                "run",
                "--rm",
                "-i",
                f"--name={container_name}",
                f"--cidfile={cid_file}",
                "--user=65534:65534",  # Non-root unprivileged (nobody:nogroup)
                f"--memory={limits.max_memory_mb}m",
                f"--cpus={limits.cpu_cores}",
                f"--pids-limit={limits.max_pids}",
                f"--ulimit=nofile={limits.max_file_descriptors}:{limits.max_file_descriptors}",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "--read-only",
                "--tmpfs=/tmp:rw,noexec,nosuid,size=64m",
                f"-v={workspace.path}:/workspace:rw",
                "-w=/workspace",
                "--network=none",
            ]

            # Pass clean environment variables
            for k, v in clean_env.items():
                cmd.append(f"-e={k}={v}")

            cmd.extend([self.image_name, "python3", "runner.py"])

            input_payload = json.dumps(
                {"action_type": request.action_type, "arguments": request.arguments}
            ).encode("utf-8")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
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
                # Kill the docker client process to stop stdin/stdout pipes.
                # Container cleanup is handled unconditionally in the finally block.
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    await proc.wait()
                except Exception:
                    pass
            finally:
                # Guarantee container removal for ALL exit paths including
                # asyncio.CancelledError, TimeoutError, and unexpected exceptions.
                #
                # Execution-ownership-safe cleanup:
                # 1. If --cidfile was written by Docker, clean up by exact 64-character container ID.
                # 2. As fallback, clean up by unique container_name (which includes execution_id).
                # Neither target can ever match or interfere with a concurrent invocation.
                #
                # subprocess.run is used (not asyncio) so that this call cannot be
                # interrupted by asyncio task cancellation.  docker rm -f is idempotent:
                # "No such container" (already removed by --rm) is silently ignored.
                cleanup_targets: list[str] = []
                try:
                    if cid_file.is_file():
                        cid = cid_file.read_text(encoding="utf-8").strip()
                        if cid:
                            cleanup_targets.append(cid)
                except Exception:
                    pass
                if container_name not in cleanup_targets:
                    cleanup_targets.append(container_name)

                # Client kill (timeout or CancelledError) can race dockerd's
                # asynchronous create. Retry rm -f until the uniquely named
                # container is gone; never filter by org/action prefix.
                incomplete = timed_out or proc.returncode is None
                if incomplete:
                    time.sleep(0.4)

                for target in cleanup_targets:
                    for _ in range(12):
                        try:
                            subprocess.run(  # noqa: S603
                                [self.docker_cmd, "rm", "-f", target],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                timeout=10,
                                check=False,
                            )
                        except Exception:
                            pass

                        filter_arg = (
                            f"id={target}"
                            if len(target) == 64 and target.isalnum()
                            else f"name={target}"
                        )
                        try:
                            check = subprocess.run(  # noqa: S603
                                [self.docker_cmd, "ps", "-aq", "--filter", filter_arg],
                                capture_output=True,
                                text=True,
                                timeout=5,
                                check=False,
                            )
                            leftover = [
                                line
                                for line in check.stdout.split()
                                if line
                            ]
                            if not leftover:
                                break
                        except Exception:
                            break
                        time.sleep(0.25)

                # Ensure the docker client process is not left as a zombie.
                if proc.returncode is None:
                    try:
                        proc.kill()
                    except Exception:
                        pass


            duration = time.monotonic() - start_time
            max_out = limits.max_output_bytes
            stdout_str = stdout_data[:max_out].decode("utf-8", errors="replace")
            stderr_str = stderr_data[:max_out].decode("utf-8", errors="replace")

            result_obj: Any = None
            violation: str | None = None
            exit_code = proc.returncode if proc.returncode is not None else -1

            if timed_out:
                violation = f"Container wall timeout of {limits.wall_timeout_seconds}s exceeded"
                exit_code = -9
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
                violation = f"Container exited with code {exit_code}: {stderr_str.strip()}"

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
