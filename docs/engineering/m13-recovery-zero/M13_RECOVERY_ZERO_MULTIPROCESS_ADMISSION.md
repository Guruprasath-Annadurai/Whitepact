# M13 RECOVERY ZERO — MULTI-PROCESS ADMISSION PROOF
## Distributed Worker Consistency, Shared Store B Authority, and Process Restart Guarantees

- **Date:** 2026-10-19
- **Author:** Antigravity FORTRESS
- **Milestone:** WhitePact M13 — Operation Recovery Zero
- **Commit Baseline:** `b896b1efb4406c03205522dce7c69855391d305b`
- **Component:** `src/responsibleai/data_governance/backup_defense.py`

---

### 1. Problem Statement & Multi-Process Threat Model (P0-05)

In enterprise deployments, WhitePact runs across multiple container processes and worker pods (e.g., Gunicorn/Uvicorn multi-worker configurations or Kubernetes replicas).

#### Threat Model:
1. **Split-Brain Readiness:** Worker A recovers and sets its in-memory gate to `READY`. Worker B starts without receiving the in-memory signal and remains `RECONCILING` or `FAILED`. Alternatively, Worker A detects a corruption and marks `FAILED`, while Worker B continues serving traffic as `READY`.
2. **Process Restart Race:** A worker crashes or restarts while recovery is in progress (`RECONCILING` or `RESTORE_PENDING`). Upon restart, does the new process correctly inherit the incomplete state, or does it fail open to `READY`?
3. **Cache Drift:** Changes committed to Store B by an operator recovery run must be immediately visible to all active workers without requiring process restarts.

---

### 2. Multi-Process Architecture & Guarantees

#### Core Invariants:
1. **Single Durable Source of Truth:** `DurableLifecycleStateProvider` utilizes SQLite with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and `PRAGMA synchronous=NORMAL`, enabling concurrent readers across distinct OS processes.
2. **Zero In-Memory Stale State in Durable Mode:** When `RestoreReadinessGate` is backed by `DurableLifecycleStateProvider`, the `state` property never caches the lifecycle state in memory. Every access to `gate.state` or `gate.is_admitted()` queries the persisted Store B state and verifies cryptographic integrity.
3. **Cryptographic Integrity Fencing Across Processes:** If an attacker modifies or corrupts Store B on disk while processes are running, all workers detect HMAC mismatch on their next admission check and immediately transition to `FAILED`.

---

### 3. Empirical Verification & Multi-Process Evidence

Test case: `test_p0_05_multi_process_consistent_evaluation_against_shared_store_b` in `tests/test_m13_recovery_zero_p0_reproducers.py`.

#### Empirical Results:
1. **Initial Blocked State Across Workers:** Two separate `RestoreReadinessGate` instances initialized in separate contexts against Store B in `RECONCILING` state:
   - Worker 1: `state == RECONCILING`, `is_admitted() == False`
   - Worker 2: `state == RECONCILING`, `is_admitted() == False`
2. **Synchronized Operator Transition to READY:**
   - Operator advances Store B to `READY` with valid HMAC.
   - Worker 1 immediately evaluates `state == READY`, `is_admitted() == True`.
   - Worker 2 immediately evaluates `state == READY`, `is_admitted() == True`.
3. **Cross-Process Failure Propagation:**
   - Operator transitions Store B to `FAILED`.
   - Both Worker 1 and Worker 2 immediately evaluate `state == FAILED`, `is_admitted() == False`.
4. **Subprocess Isolation:** An independent Python subprocess spawned with `subprocess.run` reading the shared Store B confirms identical admission state.

---

### 4. Architectural Limitations & Boundaries

- **Local In-Memory Providers:** `InMemoryLifecycleStateProvider` is strictly for unit testing. Multi-process production deployments MUST configure `WHITEPACT_STORE_B_PATH` to enable `DurableLifecycleStateProvider`.
- **NFS / Network File Systems:** If Store B is hosted on a shared network file system (NFS/CIFS), NFS file locking semantics must support SQLite WAL mode (`fcntl` locking). Local SSD or enterprise block storage is strongly recommended for Store B.
