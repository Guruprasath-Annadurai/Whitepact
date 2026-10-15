# WHITEPACT — NATIVE LINUX CONTAINMENT & ISOLATION REPORT

**Document ID:** WP-M12S-ISOL-008  
**Classification:** RUNTIME ISOLATION & KERNEL CONTAINMENT SPECIFICATION  
**Audience:** Infrastructure Engineers, SREs, Security Qualification Leads  
**Module:** `responsibleai.isolation.container_backend`  
**Status:** QUALIFIED

---

## 1. CONTAINMENT PHILOSOPHY & THREAT MODEL

AI agents generate and execute arbitrary code, shell commands, and untrusted file operations. WhitePact enforces an absolute kernel security boundary:

> **Untrusted agent execution must NEVER share memory, process namespace, or root privileges with the WhitePact governance control plane.**

In production environments, in-process execution is structurally blocked by `InternalToolExecutor`. All tool actions execute inside transient OCI containers managed by `ContainerIsolationBackend`.

---

## 2. LINUX KERNEL & OCI CONTAINER SANDBOX SPECIFICATION

Every isolated container spawned by WhitePact is launched with the following mandatory security arguments:

```bash
docker run --rm \
  --user 10001:10001 \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --network none \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --memory 512m \
  --cpus 1.0 \
  --pids-limit 64 \
  --env-file <sanitized_env_file> \
  --volume <ephemeral_workspace>:/workspace:rw \
  <isolated_image>
```

### Security Control Breakdown:

| Parameter | Linux Kernel Mechanism | Security Function |
| :--- | :--- | :--- |
| `--user 10001:10001` | Linux UID/GID namespaces | Runs as non-root unprivileged service user (`nobody`/`wp-agent`). Prevents root filesystem modification or daemon escalation. |
| `--read-only` | VFS Mount Flags (`MS_RDONLY`) | Mounts root `/` read-only. Prevents malware persistence, binary tampering, or system file manipulation. |
| `--cap-drop ALL` | POSIX Capabilities | Strips all 41 Linux capabilities (`CAP_NET_RAW`, `CAP_SYS_ADMIN`, `CAP_CHOWN`, etc.). Blocks privilege escalation. |
| `--security-opt no-new-privileges:true` | PR_SET_NO_NEW_PRIVS prctl | Prevents setuid/setgid binaries (like `sudo` or `pkexec`) from gaining elevated privileges. |
| `--network none` | Linux Network Namespace (`CLONE_NEWNET`) | Disables all network egress. The container possesses only a loopback device with zero external interface. Blocks data exfiltration. |
| `--tmpfs /tmp:...` | tmpfs with `noexec,nosuid` | Ephemeral memory-backed `/tmp` mount. Blocks executable binary drops and execution from temporary directories. |
| `--memory 512m` | Cgroups v2 `memory.max` | Hard upper memory ceiling. Prevents memory exhaustion (OOM) attacks on the host. |
| `--cpus 1.0` | Cgroups v2 `cpu.max` | CFS bandwidth enforcement. Prevents CPU starvation or cryptomining. |
| `--pids-limit 64` | Cgroups v2 `pids.max` | Process ceiling. Renders fork bombs completely harmless. |

---

## 3. ZERO CONTROL-PLANE SECRETS IN ENVIRONMENT

A common vulnerability in containerized runners is leaking control-plane environment variables (e.g., `DATABASE_URL`, `REDIS_PASSWORD`, `AWS_SECRET_ACCESS_KEY`) into the guest container via inherited `-e` flags.

### WhitePact Sanitation Invariant:
- `build_isolated_environment()` constructs a strict allowlist of environment variables:
  - Allowed: `PYTHONPATH`, `LANG`, `LC_ALL`, and explicitly declared agent inputs.
  - Denied & Filtered: Any key containing `SECRET`, `KEY`, `PASS`, `URL`, `TOKEN`, `CREDENTIAL`, or `AUTH`.
- Verified by automated sweep `test_secrets_never_logged_sweep.py`.

---

## 4. CRASH & TIMEOUT QUALIFICATION

1. **Deterministic Execution Timeout:**
   Containers are monitored with an asynchronous watchdog timer (default: 30s). On timeout, the backend sends `SIGKILL` to the container ID and forces cleanup via `--rm`.
2. **Ephemeral Workspace Shredding:**
   The host workspace directory created for the container execution is mounted from a temporary location (`tempfile.mkdtemp()`) and wiped securely upon completion.
3. **Emergency Production Gate:**
   `unisolated_execution_allowed()` returns `False` when `ENVIRONMENT=production`. Any attempt to set `WHITEPACT_ALLOW_UNISOLATED_EXECUTION=1` in production raises a fatal `IsolationError` and crashes the gateway to prevent fail-open execution.
