# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical PostgreSQL lock order for Phase 7A multi-row security transactions.

Every issuance, admission, backend-start, final CAS, and reaper path that
touches more than one of these rows MUST acquire locks in this order.
Never lock a later row then an earlier row.

Order (Gate A / Phase 7A):
  organization governance row
  -> governance epoch
  -> execution request
  -> authorization
  -> attempt
  -> worker lease / fence
  -> outbox / effect state
  -> nonces
  -> approvals

On deadlock or serialization failure: do not perform a physical effect;
fail closed; bounded retry is allowed only before the side-effect
uncertainty boundary.
"""

from __future__ import annotations

# 1 = lock first. Names match intended table/row identities, not Redis keys.
CANONICAL_LOCK_ORDER: tuple[str, ...] = (
    "organizations",
    "governance_revocation_epochs",
    "runtime_execution_requests",
    "governance_execution_authorizations",
    "runtime_execution_attempts",
    "runtime_worker_leases",
    "runtime_execution_fences",
    "runtime_execution_dispatch_outbox",
    "governance_execution_nonces",
    "governance_approvals",
)
