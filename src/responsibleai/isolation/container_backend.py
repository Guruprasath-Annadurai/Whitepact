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
import tempfile
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from responsibleai.isolation.backend import IsolationBackend
from responsibleai.isolation.environment import build_isolated_environment
from responsibleai.isolation.errors import (
    IsolationBackendUnavailableError,
    IsolationPolicyViolationError,
)
from responsibleai.isolation.filesystem import EphemeralWorkspace, grant_container_read
from responsibleai.isolation.models import ExecutionOutcome, IsolatedExecutionRequest, NetworkPolicy

logger = logging.getLogger(__name__)

# A stock interpreter image does not contain this package. Reporting that
# ImportError as a successful echo executed nothing and still looked allowed.
CONTAINER_RUNNER_SOURCE = """
import sys
import json
import asyncio

async def main():
    try:
        raw_input = sys.stdin.read()
        data = json.loads(raw_input)
        action_type = data["action_type"]
        arguments = data["arguments"]
        try:
            from responsibleai.mcp.tools import dispatch_tool
        except ImportError as exc:
            sys.stdout.write(json.dumps({
                "status": "error",
                "error": "isolated runtime unavailable: " + str(exc),
            }))
            raise SystemExit(1)
        res = await dispatch_tool(action_type, arguments)
        sys.stdout.write(json.dumps({"status": "success", "result": res}))
    except SystemExit:
        raise
    except Exception as e:
        sys.stdout.write(json.dumps({"status": "error", "error": str(e)}))
        raise SystemExit(1)

if __name__ == "__main__":
    asyncio.run(main())
"""

ISOLATION_IMAGE_ENV = "WHITEPACT_ISOLATION_IMAGE"
DEFAULT_ISOLATION_IMAGE = "python:3.11-slim"

# Caller workspace files must not be able to occupy the process entrypoint.
_RESERVED_RUNNER_NAME = "runner.py"
_TRUSTED_RUNNER_MOUNT = "/opt/whitepact/runner.py"


def normalized_workspace_path(rel_path: object) -> str | None:
    """Return a workspace-relative posix path, or None when it is not safe.

    ``None`` means the name is absolute, empty, or contains a parent
    segment. Callers reject those names instead of resolving them.
    """
    if not isinstance(rel_path, str) or not rel_path or "\x00" in rel_path:
        return None
    if rel_path.startswith(("/", "\\")) or Path(rel_path).is_absolute():
        return None
    parts: list[str] = []
    for part in Path(rel_path).parts:
        if part in {"", ".."} or "\x00" in part:
            return None
        if part == ".":
            continue
        parts.append(part)
    if not parts:
        return None
    return "/".join(parts)


def is_reserved_runner_path(rel_path: object) -> bool:
    """True when a caller path would collide with the trusted entrypoint name."""
    normalized = normalized_workspace_path(rel_path)
    if normalized is None:
        return True
    return Path(normalized).name == _RESERVED_RUNNER_NAME


def _runner_error(stdout: str) -> str | None:
    """The runner's own error message, if it wrote one; bounded and never raises."""
    try:
        parsed = json.loads(stdout)
    except ValueError:
        return None
    if isinstance(parsed, dict) and parsed.get("status") == "error":
        message = str(parsed.get("error", "")).strip()
        if message:
            return message[:500]
    return None


class DockerContainerBackend(IsolationBackend):
    """Docker container execution backend providing OCI containment."""

    def __init__(
        self,
        *,
        image_name: str | None = None,
        docker_cmd: str | None = None,
    ) -> None:
        # The image must contain WhitePact (see Dockerfile.isolation): the trusted runner
        # imports responsibleai inside the container. The stock python image does not, so
        # it can only ever fail. Operators set WHITEPACT_ISOLATION_IMAGE to an approved,
        # digest-pinned image; an explicit argument wins.
        self.image_name = (
            image_name or os.environ.get(ISOLATION_IMAGE_ENV) or DEFAULT_ISOLATION_IMAGE
        )
        self.docker_cmd = docker_cmd or shutil.which("docker") or "docker"
        # Tests that measure cgroup behavior set this on the instance.
        # Request workspace files cannot set it. IsolationBroker never does.
        self._containment_probe_enabled = False

    def trusted_runner_source(self) -> str:
        """The only program the container is started with."""
        return CONTAINER_RUNNER_SOURCE

    def _runner_source_for(self, workspace_files: Mapping[str, str | bytes]) -> str:
        if not self._containment_probe_enabled:
            return self.trusted_runner_source()
        probe = workspace_files.get(_RESERVED_RUNNER_NAME)
        if isinstance(probe, str):
            return probe
        return self.trusted_runner_source()

    def _reject_untrusted_workspace(self, workspace_files: object) -> Mapping[str, str | bytes]:
        if not isinstance(workspace_files, Mapping):
            raise IsolationPolicyViolationError(
                "workspace_files must be a mapping of relative paths to file contents."
            )
        for rel_path in workspace_files:
            if is_reserved_runner_path(rel_path) and not (
                self._containment_probe_enabled and rel_path == _RESERVED_RUNNER_NAME
            ):
                raise IsolationPolicyViolationError(
                    "Caller input cannot replace the trusted container runner."
                )
        return workspace_files

    def _install_trusted_runner(self, source: str) -> Path:
        runner_dir = Path(tempfile.mkdtemp(prefix="wp_trusted_runner_"))
        os.chmod(runner_dir, 0o700)
        target = runner_dir / _RESERVED_RUNNER_NAME
        target.write_text(source, encoding="utf-8")
        # 0o400 plus a grant to the container UID alone (ACL, or chown as root). A bind
        # mounted file keeps its host owner and mode on Linux and the container runs as an
        # unprivileged UID, so a bare 0o400 made the runner unreadable (EACCES) and every
        # isolated execution failed. The file is never world-readable and is mounted :ro.
        try:
            grant_container_read(target)
        except Exception:
            shutil.rmtree(runner_dir, ignore_errors=True)
            raise
        if target.read_text(encoding="utf-8") != source:
            raise IsolationPolicyViolationError("Trusted runner was modified after install.")
        return target

    def is_available(self) -> bool:
        """Check if docker binary is present and daemon responds.

        Uses an argv subprocess with shell=False. The docker executable is
        never interpolated into a shell string.
        """
        executable = self.docker_cmd
        if os.path.sep in executable or executable.startswith("."):
            if not os.path.isfile(executable) or not os.access(executable, os.X_OK):
                return False
        elif shutil.which(executable) is None:
            return False
        try:
            completed = subprocess.run(
                [executable, "info"],
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
                check=False,
            )
            return completed.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False
        except Exception:
            return False

    def _remove_containers(
        self,
        targets: list[str],
        *,
        stable_seconds: float,
        wait_seconds: float,
    ) -> None:
        """Remove uniquely named containers, waiting out late dockerd registration.

        Synchronous on purpose so it can run in a worker thread. Callers must
        not run this on the asyncio event loop.
        """
        deadline = time.monotonic() + wait_seconds
        gone_since: dict[str, float | None] = {target: None for target in targets}
        while time.monotonic() < deadline:
            remaining = False
            for target in targets:
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
                exists = False
                try:
                    check = subprocess.run(  # noqa: S603
                        [self.docker_cmd, "inspect", target],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                        check=False,
                    )
                    exists = check.returncode == 0
                except Exception:
                    exists = False
                if exists:
                    gone_since[target] = None
                    remaining = True
                    continue
                if stable_seconds <= 0:
                    continue
                now = time.monotonic()
                if gone_since[target] is None:
                    gone_since[target] = now
                    remaining = True
                elif now - gone_since[target] < stable_seconds:  # type: ignore[operator]
                    remaining = True
            if not remaining:
                return
            time.sleep(0.2)

    async def _remove_containers_uninterruptible(
        self,
        targets: list[str],
        *,
        stable_seconds: float,
        wait_seconds: float,
    ) -> None:
        """Run container removal off the event loop, even if this task is cancelled."""
        current = asyncio.current_task()
        restored = 0
        if current is not None and hasattr(current, "uncancel"):
            while current.cancelling() > 0:
                current.uncancel()
                restored += 1
        try:
            await asyncio.shield(
                asyncio.to_thread(
                    self._remove_containers,
                    targets,
                    stable_seconds=stable_seconds,
                    wait_seconds=wait_seconds,
                )
            )
        finally:
            for _ in range(restored):
                if current is not None:
                    current.cancel()

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
        workspace_files = self._reject_untrusted_workspace(request.workspace_files)
        runner_source = self._runner_source_for(workspace_files)
        staged_files = {
            path: content
            for path, content in workspace_files.items()
            if not (self._containment_probe_enabled and path == _RESERVED_RUNNER_NAME)
        }

        clean_env = build_isolated_environment(
            organization_id=request.organization_id,
            action_id=request.action_id,
            extra_env=request.environment_overrides,
            inherit_safe_host_vars=False,  # Container has its own isolated OS environment
        )

        limits = request.profile.resources
        execution_id = uuid.uuid4().hex[:12]
        container_prefix = f"wp_iso_{request.organization_id}_{request.action_id}"[:63].rstrip(
            "_-."
        )
        container_name = f"{container_prefix}_{execution_id}"
        start_time = time.monotonic()

        runner_host = self._install_trusted_runner(runner_source)
        try:
            with EphemeralWorkspace(request.action_id, request.organization_id) as workspace:
                workspace.populate(staged_files)
                # Host tree stays 0700/0600. Container UID 65534 is granted a
                # narrowly scoped ACL (or chown when the host is root). Never 01777.
                workspace.prepare_for_container(uid=65534, gid=65534)

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
                    f"-v={runner_host}:{_TRUSTED_RUNNER_MOUNT}:ro",
                    "-w=/workspace",
                    "--network=none",
                ]
                if runner_host.read_text(encoding="utf-8") != runner_source:
                    raise IsolationPolicyViolationError(
                        "Trusted runner changed before the container was started."
                    )

                # Pass clean environment variables
                for k, v in clean_env.items():
                    cmd.append(f"-e={k}={v}")

                cmd.extend([self.image_name, "python3", _TRUSTED_RUNNER_MOUNT])

                input_payload = json.dumps(
                    {"action_type": request.action_type, "arguments": request.arguments}
                ).encode("utf-8")

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                from responsibleai.isolation.in_flight import InFlightExecutionRegistry

                registry = InFlightExecutionRegistry.get_instance()

                async def _terminate_container() -> bool:
                    if proc.returncode is None:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        for _ in range(5):
                            await asyncio.sleep(0.02)
                            if proc.returncode is not None:
                                break
                            try:
                                wpid, _ = os.waitpid(proc.pid, os.WNOHANG)
                                if wpid == proc.pid:
                                    break
                            except ChildProcessError:
                                break

                    # 1. Force remove the container via docker rm -f
                    rm_res = subprocess.run(
                        [self.docker_cmd, "rm", "-f", container_name],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    rm_err = rm_res.stderr.lower()
                    is_absent = (
                        "no such container" in rm_err
                        or "no such object" in rm_err
                        or "not found" in rm_err
                    )
                    if rm_res.returncode != 0 and not is_absent:
                        raise RuntimeError(
                            f"Docker rm -f failed for {container_name} (rc={rm_res.returncode}): {rm_res.stderr.strip()}"
                        )

                    # 2. Actively verify container absence or confirmed stoppage via inspect
                    inspect_res = subprocess.run(
                        [
                            self.docker_cmd,
                            "inspect",
                            "-f",
                            "{{.State.Status}} {{.State.Running}}",
                            container_name,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    if inspect_res.returncode == 0:
                        parts = inspect_res.stdout.strip().lower().split()
                        status = parts[0] if parts else ""
                        is_running = parts[1] if len(parts) > 1 else ""
                        if is_running == "true" or status in {"running", "restarting", "paused"}:
                            raise RuntimeError(
                                f"Container {container_name} is still running after termination attempt (status={status})."
                            )
                        return True
                    else:
                        insp_err = inspect_res.stderr.lower()
                        if (
                            "no such container" in insp_err
                            or "no such object" in insp_err
                            or "not found" in insp_err
                        ):
                            return True
                        # Nonzero inspection error (daemon disconnect, permission denied, timeout)
                        # Must NOT be marked successful without authoritative proof of containment
                        raise RuntimeError(
                            f"Docker inspect failed authoritatively confirming containment for {container_name} (rc={inspect_res.returncode}): {inspect_res.stderr.strip()}"
                        )

                try:
                    await registry.register(
                        execution_id=execution_id,
                        organization_id=request.organization_id,
                        action_id=request.action_id,
                        task=asyncio.current_task(),
                        terminate_callback=_terminate_container,
                        admission_epoch=request.admission_epoch,
                    )
                except PermissionError as exc:
                    return ExecutionOutcome(
                        action_id=request.action_id,
                        exit_code=-9,
                        result_payload=None,
                        stdout="",
                        stderr=str(exc),
                        duration_seconds=time.monotonic() - start_time,
                        violation=f"Execution authorization revoked in-flight: {exc}",
                    )

                timed_out = False
                revoked_in_flight = False
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
                except asyncio.CancelledError:
                    revoked_in_flight = True
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    try:
                        await proc.wait()
                    except Exception:
                        pass
                finally:
                    await registry.unregister(execution_id)
                    duration = time.monotonic() - start_time
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
                    await self._remove_containers_uninterruptible(
                        cleanup_targets,
                        stable_seconds=3.0 if incomplete else 0.0,
                        wait_seconds=12.0 if incomplete else 2.0,
                    )

                    # Ensure the docker client process is not left as a zombie.
                    if proc.returncode is None:
                        try:
                            proc.kill()
                        except Exception:
                            pass

                max_out = limits.max_output_bytes
                stdout_str = stdout_data[:max_out].decode("utf-8", errors="replace")
                stderr_str = stderr_data[:max_out].decode("utf-8", errors="replace")

                result_obj: Any = None
                violation: str | None = None
                exit_code = proc.returncode if proc.returncode is not None else -1

                if timed_out:
                    violation = f"Container wall timeout of {limits.wall_timeout_seconds}s exceeded"
                    exit_code = -9
                elif revoked_in_flight:
                    violation = "Execution revoked in-flight: container terminated immediately"
                    exit_code = -15
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
                    # The trusted runner reports its own failure as JSON on stdout, so stderr
                    # alone is often just Docker's pull chatter. Prefer the runner's error.
                    detail = _runner_error(stdout_str) or stderr_str.strip()
                    violation = f"Container exited with code {exit_code}: {detail}"

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
        finally:
            shutil.rmtree(runner_host.parent, ignore_errors=True)
