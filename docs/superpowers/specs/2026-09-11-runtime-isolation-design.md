# WhitePact Enterprise Phase 2: Runtime Isolation & Independent Execution Plane Design

**Date:** 2026-09-11  
**Status:** Approved for Implementation (Autonomous Adversarial Security Engineering)  
**Author:** Principal Runtime Security Architect & Linux/Container Isolation Specialist  
**Baseline Commit:** `93c8e88c89c373d24d35ff074a283d8c61e065e1`  
**Branch:** `feature/runtime-isolation-phase2`  

---

## 1. Executive Summary & Core Doctrine

The fundamental security doctrine of WhitePact is:
> **"The agent may think freely. It may plan freely. But it cannot act outside independently enforced authority."**

Prior to Phase 2, WhitePact's execution runtime was strictly in-process (`InternalToolExecutor` calling `dispatch_tool` inside the same Python process as the governance control plane). Empirical red-team findings confirmed:
- Control plane environment secrets (`DATABASE_URL`, `REDIS_URL`, `RAI_FIELD_ENCRYPTION_KEY`, JWT keys) are fully visible in the execution context.
- Unrestricted host filesystem read/write/traversal access.
- Direct reachability to control plane PostgreSQL/SQLite databases and Redis instances.
- Reachability to localhost (`127.0.0.1`) and exposed Docker sockets (`/var/run/docker.sock`).
- Orphaned child process survival upon asyncio cancellation with zero resource limits (CPU, memory, PID, FD).

Phase 2 establishes a cryptographically bound, independently isolated execution plane where:
1. Untrusted or semi-trusted tool/agent code executes in an isolated environment.
2. Control plane secrets are never inherited or leaked into the execution plane.
3. Network access defaults to `NETWORK_NONE` unless explicitly authorized.
4. Ephemeral workspaces are strictly cleaned up, and process trees are terminated with SIGKILL on timeouts or failures.
5. Production runtime strictly requires container/OCI isolation, failing closed if container runtime is unavailable, and forbidding silent fallback to local subprocess execution.

---

## 2. Architecture: Control Plane vs. Execution Plane Boundary

```
+-------------------------------------------------------------------------+
|                       WHITEPACT CONTROL PLANE                          |
|                                                                         |
|  - Decision Engine & Gateway (`evaluate()`)                             |
|  - AuthorityResolver & Durable Nonce Admission (`admit_execution()`)    |
|  - Evidence Repository & Signing Keys                                   |
|  - Database Connection Pool (PostgreSQL / SQLite)                       |
|  - Redis Pool & Master Encryption Keys                                  |
|                                                                         |
|                        IsolationBroker                                  |
|                               |                                         |
|                   IsolatedExecutionRequest                              |
|                   (Profile, Strict Limits, Allowlist Env)               |
+-------------------------------|-----------------------------------------+
                                |  [ISOLATION BOUNDARY]
                                |  - No shared memory / call frames
                                |  - Zero control-plane secrets in env
                                |  - Isolated PID / Mount / Net namespace
                                v
+-------------------------------------------------------------------------+
|                  INDEPENDENT EXECUTION PLANE                            |
|                                                                         |
|  Backends:                                                              |
|    1. DockerContainerBackend (Production & Enterprise Hardened)         |
|    2. LocalSubprocessBackend (Strictly LOCAL_DEV_ONLY)                  |
|                                                                         |
|  Containment Properties:                                                |
|  - Read-Only Root Filesystem (except ephemeral /tmp /workspace)         |
|  - Unprivileged Non-Root User (UID/GID 10001:10001 or nobody)           |
|  - Network default: None (`--network none` / blocked loopback)          |
|  - Hard Resource Cgroups: CPU (0.5), Memory (256MB), PIDs (32)          |
|  - Process Group Supervision: All children killed on exit               |
|  - Output Clamping & Sanitization                                       |
+-------------------------------------------------------------------------+
                                |
                                | Sanitized ExecutionOutcome Only
                                v
+-------------------------------------------------------------------------+
|                        CANONICAL EVIDENCE PLANE                         |
|  (Hash of request, profile, limits, stdout/stderr, exit_code, metrics) |
+-------------------------------------------------------------------------+
```

---

## 3. Core Component Design

### 3.1 Module Organization (`src/responsibleai/isolation/`)
- `__init__.py`: Package exports for public isolation API.
- `models.py`: Data models (`IsolationProfile`, `NetworkPolicy`, `ResourceLimits`, `IsolatedExecutionRequest`, `ExecutionOutcome`, `BackendMode`).
- `errors.py`: Strict error hierarchy (`IsolationError`, `IsolationBackendUnavailableError`, `IsolationPolicyViolationError`, `ResourceLimitExceededError`, `TimeoutExceededError`, `InvalidBackendModeError`).
- `environment.py`: Clean environment constructor with strict allowlist and zero control-plane secret leakage.
- `filesystem.py`: Ephemeral workspace lifecycle manager with traversal defense and guaranteed cleanup.
- `backend.py`: Base abstract protocol `IsolationBackend`.
- `subprocess_backend.py`: `LocalSubprocessBackend` implementing process-group isolation, resource limits via `resource` module, env scrubbing, and timeout enforcement. Gated to `LOCAL_DEV_ONLY`.
- `container_backend.py`: `DockerContainerBackend` implementing OCI container execution with unprivileged user, read-only rootfs, dropped capabilities, no-new-privileges, pids-limit, memory/cpu limits, and network isolation.
- `broker.py`: `IsolationBroker` coordinating profile resolution, backend selection, admission checks, execution, and outcome sanitization.

### 3.2 Isolation Profiles (`IsolationProfile`)
1. `STRICT` (Default):
   - Network: `NONE`
   - Memory Limit: 256 MB
   - CPU Quota: 0.5 cores
   - Max PIDs: 32
   - Wall Timeout: 15 seconds
   - Filesystem: Ephemeral empty directory, read-only root, no socket mounts
   - Max Output Size: 64 KB
2. `COMPLIANCE_EVAL`:
   - Network: `NONE`
   - Memory Limit: 512 MB
   - CPU Quota: 1.0 cores
   - Max PIDs: 64
   - Wall Timeout: 30 seconds
   - Filesystem: Ephemeral workspace
3. `OUTBOUND_NETWORK` (Only when permitted by authority):
   - Network: `ALLOWLISTED_EGRESS` (uses safe transport / egress IP binding)
   - Memory Limit: 256 MB
   - Max PIDs: 32
   - Wall Timeout: 30 seconds

### 3.3 Strict Environment Sanitization
Control-plane secrets are scrubbed completely.
- Deny list: Any variable matching `*KEY*`, `*SECRET*`, `*TOKEN*`, `*PASS*`, `*CRED*`, `*DATABASE*`, `*REDIS*`, `*CONN*`, `*AUTH*`, `*SESSION*`, `*PRIVATE*`, `*CERT*`, `*DSN*`, `*URL*`.
- Explicit safe allowlist only: `PATH`, `LANG`, `LC_ALL`, `PYTHONPATH` (if needed for isolated runners).
- Injected sandbox markers: `WHITEPACT_SANDBOX=1`, `WHITEPACT_TENANT_ID=<org_id>`, `WHITEPACT_ACTION_ID=<id>`.

### 3.4 Production Fail-Closed Rule
- If `WHITEPACT_ISOLATION_BACKEND=docker` (or production default), but the Docker daemon is unreachable, the system raises `IsolationBackendUnavailableError` and aborts. It NEVER falls back to local subprocess.
- `LocalSubprocessBackend` is only valid when `WHITEPACT_ISOLATION_BACKEND=local_dev` AND `ENVIRONMENT != production`.

---

## 4. Integration with `InternalToolExecutor` and Governance

`InternalToolExecutor` will accept an `IsolationBroker`:
```python
class InternalToolExecutor:
    def __init__(
        self,
        *,
        nonce_repo: ExecutionNonceRepository | None = None,
        broker: IsolationBroker | None = None,
    ) -> None:
        self._nonce_repo = nonce_repo
        self._broker = broker

    async def execute(self, authorization: ExecutionAuthorization, action: ActionRequest) -> Any:
        await admit_execution(authorization, action, self._nonce_repo)
        if self._broker is not None:
            return await self._broker.execute(authorization, action)
        # Direct fallback only when broker is not configured in unit tests
        from responsibleai.mcp.tools import dispatch_tool
        return await dispatch_tool(action.action_type, action.arguments)
```

---

## 5. Security Threat Matrix & Mitigations

| Threat Vector | Mitigation in Phase 2 |
| :--- | :--- |
| Environment Secret Leakage | Strict whitelist-only env; regex scrubbing of all sensitive keywords. |
| Host Filesystem Access | Isolated ephemeral container/tempdir; path canonicalization preventing `..` traversal. |
| Docker Socket Abuse | Never mount `/var/run/docker.sock` in container; drop capabilities. |
| Host Localhost Network Abuse | `--network none` in container; socket binding restrictions in subprocess. |
| Fork Bomb / Zombie Children | Strict PID limits (32); `os.killpg(pgrp, SIGKILL)` in cleanup handler. |
| CPU / Memory Exhaustion | Memory cgroup (256MB) / `setrlimit(RLIMIT_AS)`; CPU limit (0.5 cores). |
| Output ANSI Bombing / Hijack | Clamped to 64KB max; stripped ANSI control sequences; typed outcome struct. |
| Privilege Escalation | Container runs as non-root (UID 10001); `--security-opt no-new-privileges:true`. |
