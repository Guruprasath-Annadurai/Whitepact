# WhitePact Phase 7A — Cursor Hardening Specification Closure

**Status:** CANONICAL (Cursor hardening pass; does not open the implementation gate)
**Frozen parent:** `7bed526e3d631632b4108b0ef6c7ff13728fa914`
**Current Alembic head after this pass:** `0053` (`runtime_worker_leases` + fences + outbox)
**Phase 7A runtime migrations:** `0050` → `0053` (development/staging implementation; Production Gate B CLOSED)

This document resolves remaining architecture decisions. It does **not**
activate `PHASE7A_DISPATCHER_ENABLED`. Redis, QueueTicket, worker leases,
and billing are never execution authority.

**Canonical migration ownership:** `docs/phase7a-execution/migration-ownership.md` (implemented `0049` = org governance lifecycle).

---

## 1. Authorization lifecycle (single source of truth)

Durable authorization status is only:

- `ISSUED`
- `CONSUMED`

Expiration is derived: `expires_at > CURRENT_TIMESTAMP`.

Governance revocation is derived: authorization `issuer_epoch` compared to
current `governance_revocation_epochs.epoch` for the organization
(`scope = governance`).

Do **not** add `status = REVOKED` on the authorization row. Epoch advance
is the revocation signal. Lease rows may use `EXPIRED` / operational
`REVOKED` for **lease infrastructure only**; that is not authorization
status.

---

## 2. Governance status vs billing

Column: `organizations.governance_status`

Values: `ACTIVE` | `SUSPENDED` | `DISABLED`

Migration ownership: **`0049_add_organization_governance_status.py`**
(implemented in this hardening pass; down-revision `0048`).

- Billing (`plan`, `subscription_status`, Stripe/Paddle) controls quota
  and commercial feature access only.
- `OrgRepository.set_plan` / `apply_paddle_entitlement` MUST NOT write
  `governance_status` and MUST NOT bump the governance epoch.
- `OrgRepository.set_governance_status` is a human/admin path: updates
  status and bumps `governance` epoch in the same transaction.
- Hosted execution requires `governance_status = ACTIVE` before effect.
- `DELETING` is not used; tenant deletion remains the existing tombstone
  workflow.

---

## 3. Post-admission / pre-effect revocation

If the governance epoch changes, or the organization is no longer
`ACTIVE`, after `ADMITTED` but **before** physical effect:

**The effect MUST NOT begin.**

Final pre-effect CAS (`claim_local_effect_start` /
`claim_external_effect_transmission`) revalidates, under the canonical
lock order:

- active unexpired lease + generation
- `issuer_epoch == current governance epoch`
- `organizations.governance_status = ACTIVE`
- action digest, org, attempt, effect_id, backend_start_token_hash
- target fingerprint for external effects

On rejection, atomically:

`BACKEND_STARTING -> FAILED_PRE_EXECUTION`

`effect_state` remains `NO_EFFECT`. Physical effect authority is not
consumed. Automatic replay of that attempt is forbidden. A new attempt
requires a new authorization if the original was already `CONSUMED` at
admission; if admission itself failed, authorization remains `ISSUED`.

Once an external byte may have been sent, outcome is `UNCERTAIN`. No
automatic replay.

---

## 4. SafeNetwork ownership

Canonical owner: `src/responsibleai/net/egress.py`

- `SafeNetworkBackend` pins TCP connect to a validated IP
- `trust_env=False`
- redirects disabled at the client
- TLS verification and SNI remain on the authorized hostname
- Host header remains the authorized hostname
- post-connect peer verification **fails closed**
- CGNAT `100.64.0.0/10` is blocked under `PUBLIC_ONLY`

Do **not** add `isolation/safe_network.py`. Phase 7A executors import
`create_safe_async_client` / `SafeNetworkBackend` from `net.egress`.

---

## 5. Dispatch outbox publisher linearization

Statuses: `PENDING` → `PUBLISHING` → `PUBLISHED` → `ACKNOWLEDGED`
plus `CANCELLED` and `EXPIRED`.

**Option B (required):** atomic CAS `PENDING -> PUBLISHING` with
`publisher_id`, `claimed_at`, and claim timeout, or equivalently
`SELECT … FOR UPDATE SKIP LOCKED` then the same CAS.

Crash after claim, before Redis: claim times out; another publisher may
CAS `PUBLISHING -> PENDING` (or reclaim) and retry. Capacity reserve
must be the atomic Lua operation (section 8).

Crash after Redis, before durable `PUBLISHED`: publisher retries enqueue.
Duplicate `QueueTicket` delivery **can happen**. Downstream durable
admission/CAS is the only uniqueness boundary. Do not claim Redis queue
dedupe unless the chosen broker documents an atomic dedupe primitive.

Outbox is infrastructure, never authority.

---

## 6. effect_id

`effect_id` is a WhitePact correlation / audit / reconciliation ID. It is
durable before external transmission and stable across reconciliation.

It is **not** automatically an upstream idempotency key.

Map it to an upstream idempotency mechanism only when that upstream
documents a compatible contract. Never assume arbitrary MCP/HTTP servers
honor `X-WhitePact-Effect-ID`.

If transmission outcome is uncertain: `UNCERTAIN`, no automatic replay.

External effect MUST NOT begin without a durable `effect_id`.

---

## 7. Production rollback

While new Phase 7A tables are empty, schema downgrade of **those unused
tables** may be acceptable.

After production activity: do **not** drop execution, audit, or evidence
history as routine rollback.

Prefer: disable dispatcher (`PHASE7A_DISPATCHER_ENABLED=false`), stop
issuance, drain/reconcile, retain durable rows, revert application code
only where schema-compatible.

---

## 8. Atomic Redis capacity reservation

One Lua `EVAL` covers check + create reservation + increment tenant count
+ TTL. Release is one Lua `EVAL` covering existence + delete + decrement
with a floor of zero. Repeat reserve/release is idempotent.

Heartbeat `EXPIRE` keeps reservation TTL ≥ worker lease TTL.

Canonical scripts: `src/responsibleai/runtime/capacity_reservation.py`.

Not wired to a live dispatcher in this pass.

---

## 9. Canonical PostgreSQL lock order

See `src/responsibleai/runtime/lock_order.py`:

1. `organizations`
2. `governance_revocation_epochs`
3. `runtime_execution_requests`
4. `governance_execution_authorizations`
5. `runtime_execution_attempts`
6. `runtime_worker_leases`
7. `runtime_execution_fences`
8. `runtime_execution_dispatch_outbox`
9. `governance_execution_nonces`
10. `governance_approvals`

Deadlock / serialization failure: no physical effect; fail closed;
bounded retry only before the uncertainty boundary.

---

## 10. Phase 7A runtime migration chain (unactivated)

Current implemented head: `0049`.

Planned (not created in this pass):

- `0050_runtime_execution_requests` (was 0049 in Pass 4.4 docs)
- `0051_runtime_execution_authorizations` (was 0050)
- `0052_runtime_execution_attempts` (was 0051)
- `0053_runtime_worker_leases` including outbox + fences (was 0052)

Dispatcher remains disabled until the independent implementation gate.

---

## 11. FAILED_PRE_EXECUTION after final CAS rejection

If final CAS loses because epoch/status/lease/generation/binding/token
failed:

1. Same transaction (or a follow-up fail-closed transaction if the CAS
   UPDATE returned 0 and a dedicated terminalizer is required) sets
   attempt `BACKEND_STARTING -> FAILED_PRE_EXECUTION` only when
   `effect_state = NO_EFFECT` and `backend_start_token_hash` is cleared
   or never usable again.
2. Do not leave the attempt stuck in `BACKEND_STARTING`.
3. Reaper must treat `BACKEND_STARTING` past claim timeout with
   `NO_EFFECT` as `FAILED_PRE_EXECUTION`, never as retryable effect.

This is specification-complete; runtime tables/code are not activated.
