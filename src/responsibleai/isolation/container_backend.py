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
import functools
import hashlib
import json
import logging
import os
import shutil
import stat
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

    @staticmethod
    def _trusted_container_id(path: Path) -> str | None:
        """Read only a complete Docker creation receipt from our private directory.

        Docker writes the full ID after ContainerCreate succeeds, before start.
        No receipt means creation may still be pending and needs the stable wait.
        The caller must keep this directory private and outside container mounts.
        """
        descriptor = None
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_nlink != 1
                or info.st_size != 64
            ):
                return None
            value = os.read(descriptor, 65)
            if len(value) != 64 or any(byte not in b"0123456789abcdef" for byte in value):
                return None
            return value.decode("ascii")
        except OSError:
            return None
        finally:
            if descriptor is not None:
                os.close(descriptor)

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

        def command_timeout(maximum: float) -> float:
            budget = deadline - time.monotonic()
            if budget <= 0:
                raise TimeoutError("Container cleanup deadline exhausted")
            return min(maximum, budget)

        gone_since: dict[str, float | None] = {target: None for target in targets}
        while time.monotonic() < deadline:
            remaining = False
            for target in targets:
                try:
                    subprocess.run(  # noqa: S603
                        [self.docker_cmd, "rm", "-f", target],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=command_timeout(10),
                        check=False,
                    )
                except Exception:
                    pass
                is_absent = False
                try:
                    check = subprocess.run(  # noqa: S603
                        [self.docker_cmd, "inspect", target],
                        capture_output=True,
                        text=True,
                        timeout=command_timeout(5),
                        check=False,
                    )
                    if check.returncode != 0:
                        err = check.stderr.lower()
                        # Authoritative absence detection:
                        # Docker inspect returns "Error: No such container: <name>" or
                        # "Error: No such object: <name>". Never match broad "not found",
                        # which matches daemon/plugin errors like "authorization plugin not found".
                        has_no_such = "no such container" in err or "no such object" in err
                        is_plugin_or_daemon_err = "plugin" in err or "daemon unavailable" in err
                        if has_no_such and not is_plugin_or_daemon_err:
                            is_absent = True
                        else:
                            # Nonzero inspect with daemon error, plugin error, or disconnection: absence unconfirmed!
                            is_absent = False
                    else:
                        # Container still exists in dockerd
                        is_absent = False
                except Exception:
                    # Timeout or inspection execution error: cannot establish absence!
                    is_absent = False

                if not is_absent:
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
            time.sleep(max(0, min(0.2, deadline - time.monotonic())))

        # If deadline expires and any target was not confirmed absent, fail closed!
        unconfirmed = [
            t
            for t, g in gone_since.items()
            if g is None or (stable_seconds > 0 and (time.monotonic() - g < stable_seconds))
        ]
        if unconfirmed:
            raise RuntimeError(
                f"Container containment unconfirmed after {wait_seconds}s for targets: {unconfirmed}"
            )

    async def _remove_containers_uninterruptible(
        self,
        targets: list[str],
        *,
        stable_seconds: float,
        wait_seconds: float,
    ) -> None:
        """Run container removal off the event loop, guaranteed to finish even if cancelled."""
        loop = asyncio.get_running_loop()
        thread_future = loop.run_in_executor(
            None,
            functools.partial(
                self._remove_containers,
                targets,
                stable_seconds=stable_seconds,
                wait_seconds=wait_seconds,
            ),
        )
        await self._await_owned_completion(thread_future)

    async def _await_owned_completion(self, future: asyncio.Future) -> Any:
        """Finish an owned operation, then restore exactly the caller's cancel requests."""
        current = asyncio.current_task()
        cancellation_count = 0

        def consume_requests() -> None:
            nonlocal cancellation_count
            if current is not None:
                while current.cancelling() > 0:
                    current.uncancel()
                    cancellation_count += 1

        consume_requests()
        try:
            while not future.done():
                try:
                    await asyncio.shield(future)
                except asyncio.CancelledError:
                    # Delivery may represent requests already drained above (3.11),
                    # or several requests coalesced into one exception. Count requests.
                    consume_requests()
            return future.result()
        finally:
            if current is not None:
                for _ in range(cancellation_count):
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
        cid_directory = None
        try:
            # Docker's receipt must never be writable by the isolated workload.
            # TemporaryDirectory is 0700 and is deliberately not bind mounted.
            cid_directory = tempfile.TemporaryDirectory(prefix="wp-container-receipt-")
            cid_file = Path(cid_directory.name) / "container.cid"
            with EphemeralWorkspace(request.action_id, request.organization_id) as workspace:
                workspace.populate(staged_files)
                # Host tree stays 0700/0600. Container UID 65534 is granted a
                # narrowly scoped ACL (or chown when the host is root). Never 01777.
                workspace.prepare_for_container(uid=65534, gid=65534)

                cmd = [
                    self.docker_cmd,
                    "run",
                    "--rm",
                    "-i",
                    f"--name={container_name}",
                    f"--cidfile={cid_file}",
                    f"--label=io.whitepact.organization={hashlib.sha256(request.organization_id.encode()).hexdigest()}",
                    f"--label=io.whitepact.execution={execution_id}",
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

                # Cancellation cannot discard a subprocess whose OS creation has
                # already happened but whose asyncio handoff has not returned.
                proc = await self._await_owned_completion(
                    asyncio.create_task(
                        asyncio.create_subprocess_exec(
                            *cmd,
                            stdin=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                    )
                )

                from responsibleai.isolation.in_flight import InFlightExecutionRegistry

                registry = InFlightExecutionRegistry.get_instance()
                communication_started = False
                acknowledged_cid = None

                def creation_receipt() -> str | None:
                    nonlocal acknowledged_cid
                    if acknowledged_cid is None:
                        acknowledged_cid = self._trusted_container_id(cid_file)
                    # A verified create acknowledgement remains true if cleanup
                    # needs a same-worker retry after its private directory closes.
                    return acknowledged_cid

                async def _terminate_container() -> bool:
                    async def terminate_owned() -> bool:
                        client_completed = proc.returncode == 0
                        if proc.returncode is None:
                            try:
                                proc.kill()
                            except ProcessLookupError:
                                pass
                        drain_error = None
                        if not communication_started:
                            # Registration may deny before the normal communicate
                            # owner starts. Drain PIPEs and reap the killed client;
                            # never introduce a second reader during execution.
                            try:
                                await asyncio.wait_for(proc.communicate(), timeout=1.0)
                            except Exception as exc:
                                drain_error = exc
                        cid = creation_receipt()
                        targets = [cid, container_name] if cid is not None else [container_name]
                        # Unknown creation can arrive after an early absent result.
                        # A private full CID proves create completed; delayed start
                        # cannot recreate that removed identity.
                        await self._remove_containers_uninterruptible(
                            targets,
                            stable_seconds=0.0 if cid is not None else 3.0,
                            wait_seconds=12.0,
                        )
                        if cid is None and not client_completed:
                            raise RuntimeError(
                                "Docker creation completion unconfirmed; retaining unresolved containment"
                            )
                        if drain_error is not None:
                            raise RuntimeError(
                                "Docker client drainage/reaping unconfirmed"
                            ) from drain_error
                        return True

                    # Register awaits this callback before denying admission.
                    # Its existing unresolved contract retains failed containment.
                    return await self._await_owned_completion(
                        asyncio.create_task(terminate_owned())
                    )

                execution_owner = asyncio.current_task()

                async def register_owned():
                    entry = await registry.register(
                        execution_id=execution_id,
                        organization_id=request.organization_id,
                        action_id=request.action_id,
                        task=asyncio.current_task(),
                        terminate_callback=_terminate_container,
                        admission_epoch=request.admission_epoch,
                        container_name=container_name,
                        container_id=creation_receipt(),
                    )
                    # No await between registry acceptance and owner transfer.
                    # Rejection must see the registration task as its own caller,
                    # avoiding an extra cancellation of an uncanceled executor.
                    entry.task = execution_owner
                    return entry

                try:
                    registration = await self._await_owned_completion(
                        asyncio.create_task(register_owned())
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
                communication_started = True
                try:
                    stdout_data, stderr_data = await asyncio.wait_for(
                        proc.communicate(input=input_payload),
                        timeout=limits.wall_timeout_seconds,
                    )
                except TimeoutError:
                    timed_out = True
                except asyncio.CancelledError:
                    revoked_in_flight = True
                finally:
                    client_cleanup_error = None
                    if timed_out or revoked_in_flight or proc.returncode is None:

                        async def finish_client_io():
                            failure = None
                            if proc.returncode is None:
                                try:
                                    proc.kill()
                                except ProcessLookupError:
                                    pass
                                except Exception as exc:
                                    failure = exc
                            # wait_for has retired its communication task before
                            # entering this finally. Drain the remaining PIPEs,
                            # including cancellation before that task ever ran.
                            # Process.wait alone can hang on a full PIPE buffer.
                            try:
                                await asyncio.wait_for(proc.communicate(), timeout=1.0)
                            except (Exception, asyncio.CancelledError) as exc:
                                failure = exc
                            return failure

                        client_cleanup_error = await self._await_owned_completion(
                            asyncio.create_task(finish_client_io())
                        )
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
                    cid = creation_receipt()
                    cleanup_targets = [cid, container_name] if cid is not None else [container_name]

                    # Client kill (timeout or CancelledError) can race dockerd's
                    # asynchronous create. Retry rm -f until the uniquely named
                    # container is gone; never filter by org/action prefix.
                    incomplete = timed_out or proc.returncode is None or revoked_in_flight
                    creation_settled = cid is not None or proc.returncode == 0
                    cleanup_error: Exception | None = None
                    try:
                        await self._await_owned_completion(
                            asyncio.create_task(
                                self._remove_containers_uninterruptible(
                                    cleanup_targets,
                                    stable_seconds=3.0 if not creation_settled else 0.0,
                                    wait_seconds=12.0
                                    if incomplete or not creation_settled
                                    else 2.0,
                                )
                            )
                        )
                        if not creation_settled:
                            raise RuntimeError(
                                "Docker creation completion unconfirmed; retaining unresolved containment"
                            )
                        if client_cleanup_error is not None:
                            raise RuntimeError(
                                "Docker client drainage/reaping unconfirmed"
                            ) from client_cleanup_error
                    except Exception as exc:
                        cleanup_error = exc
                        logger.critical(
                            "CONTAINER_CLEANUP_FAILED_PRESERVING_UNRESOLVED: %s for org %s (%s)",
                            execution_id,
                            request.organization_id,
                            exc,
                        )

                    # Ensure the docker client process is not left as a zombie.
                    if proc.returncode is None:
                        try:
                            proc.kill()
                        except Exception:
                            pass

                    # Unregister AFTER container removal is confirmed, ensuring
                    # active tracking remains valid until containment is complete.
                    # CRITICAL INVARIANT: If removal failed or absence is unconfirmed,
                    # DO NOT unregister! Retain in registry tracking as unresolved containment.
                    async def finish_tracking() -> None:
                        if cleanup_error is not None:
                            async with registry._lock:
                                registration.termination_attempts += 1
                                registration.containment_status = "unresolved"
                                registration.last_termination_error = str(cleanup_error)
                                registry._unresolved[execution_id] = registration
                                registry._active.pop(execution_id, None)
                                from responsibleai.isolation.in_flight import (
                                    _record_cross_worker_registration,
                                )

                                try:
                                    _record_cross_worker_registration(registration)
                                except Exception:
                                    logger.critical(
                                        "UNRESOLVED_TRACKING_PERSISTENCE_FAILED: %s", execution_id
                                    )
                        else:
                            await registry.unregister(execution_id)

                    await self._await_owned_completion(asyncio.create_task(finish_tracking()))
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
            if cid_directory is not None:
                cid_directory.cleanup()
            shutil.rmtree(runner_host.parent, ignore_errors=True)
