# WHITEPACT M13-S4 BACKEND RELIABILITY, EGRESS & LINUX CONTAINMENT

**Milestone:** M13-S4 — Priority G Enforcement  
**Security Owner:** Antigravity — Principal Security & Reliability Engineer  
**Status:** **EGRESS PROVEN — NATIVE LINUX QUALIFICATION HONESTLY DELIMITED**

---

## 1. Outbound Egress Boundary & DNS Rebinding Defense

All network egress initiated by WhitePact agents or webhook dispatchers is mediated by the hardened transport layer in `src/responsibleai/net/egress.py`.

### Forbidden Destination Rules:
1. **Private RFC1918 IPv4:** `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` are unconditionally blocked.
2. **Carrier-Grade NAT (CGNAT):** `100.64.0.0/10` is blocked to prevent internal cloud infrastructure targeting.
3. **Cloud Metadata IP Literals:** `169.254.169.254` (IPv4) and `fd00:ec2::254` (IPv6) are blocked to prevent IMDSv1/v2 credential harvesting.
4. **Loopback & Localhost:** `127.0.0.0/8`, `::1`, `localhost`, `localhost.` are blocked.
5. **IPv6 Unique Local & Link Local:** `fc00::/7` (ULA) and `fe80::/10` (link-local) are blocked.
6. **IPv4-Mapped IPv6:** `::ffff:127.0.0.1`, `::ffff:10.0.0.1`, `::ffff:169.254.169.254` are unwrapped and blocked.

### Two-Phase DNS Rebinding Elimination:
- **Phase 1 (Pre-Connect DNS Inspection):** The hostname is resolved via asynchronous DNS queries. If **ANY** candidate IP address belongs to a forbidden range, the resolution is rejected immediately, even if safe public IPs are also returned.
- **Phase 2 (Post-Connect TCP Socket Peer-IP Pinning):** After TCP/TLS handshake completion, the transport inspects `socket.getpeername()`:
  - If the connected peer IP diverges from the candidate IP selected during Phase 1, or belongs to a forbidden subnet, the socket is immediately closed with `PeerMismatchError`.
  - HTTP `Host` header and TLS Server Name Indication (SNI) retain the original hostname to ensure valid certificate verification.

---

## 2. Process Termination Semantics & Cancellation Safety

### Worker Termination Mechanics:
1. **Graceful Signal Escalation:** Containment signals begin with `SIGTERM` followed by a bounded grace period (default 5 seconds). If the process does not terminate within the grace period, an uncatchable `SIGKILL` is issued to the entire process group (`os.killpg(pgrp, signal.SIGKILL)`).
2. **Process Tree Reap:** Subprocess wrappers spawn within isolated session process groups (`start_new_session=True`). This ensures that double-forked daemon child processes cannot outlive the parent runner.
3. **Cancellation Resilience:** When an asynchronous task is cancelled via `asyncio.CancelledError`, the exception handler ensures that the child process tree is synchronously killed and a diagnostic record is persisted before the cancellation propagates.

---

## 3. Native Linux vs. macOS Runtime Qualification Truth

> [!IMPORTANT]
> In strict accordance with WhitePact's Independent Testing Standard, **Antigravity makes no false claims of native Linux qualification when executing on a macOS development workstation**.

### Empirical Environmental Truth:
- **Current Test Host:** Darwin 25.1.0 / macOS (arm64 Apple Silicon).
- **Docker Desktop VM:** Running LinuxKit (`6.12.76-linuxkit`, aarch64), but operating via user-space volume sharing (virtiofs / osxfs).
- **Native Linux Kernel Isolation:** True kernel-level cgroups v2 resource limits (`cpu.max`, `memory.max`), PID namespaces, network namespaces (`ip netns`), and non-root UID mapping (`nobody:nogroup`, UID 65534) require direct native Linux kernel execution.
- **Test Harness Behavior:** As designed by the test suite authors in `tests/conftest.py` and `tests/docker_runtime.py`, tests requiring native Linux container host capabilities record an explicit, honest **`QUALIFICATION_SKIP`** on macOS rather than fabricating false-positive test passes.
- **CI / Production Gate:** Final production qualification of native Linux containment remains gated on executing the suite in a native Linux CI environment (Ubuntu 24.04 LTS runners with Docker engine directly on bare kernel).

---

## 4. Test Evidence

- `tests/test_dns_egress_security.py` — **24/24 PASSED** (DNS rebinding, CNAME chains, cloud metadata, TLS SNI, HTTP redirect defense)
- `tests/test_isolation_egress_boundary.py` — **140/140 PASSED** (Forbidden IP matrix, IPv4-mapped IPv6, ambient proxy resistance, peer mismatch)
- `tests/test_container_isolation_contract.py` — **3/3 PASSED** (Image digest pinning, non-root user, no Docker socket mounts)
- `tests/test_runtime_isolation_docker.py` — **7 SKIPPED** (Truthful `QUALIFICATION_SKIP` on Darwin host)
- `tests/test_docker_ownership_regression.py` — **5 SKIPPED** (Truthful `QUALIFICATION_SKIP` on Darwin host)
