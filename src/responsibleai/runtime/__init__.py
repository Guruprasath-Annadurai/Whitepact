# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Phase 7A runtime foundations.

Importing this package is not an activation gate. The dispatcher starts
only through ``start_phase7a_dispatcher`` after an explicit development
or staging flag. Production Gate B remains CLOSED.

Redis, QueueTicket, worker leases, subscriptions, and API keys are never
execution authority. The agent may think freely and plan freely. It cannot
act outside independently enforced authority.
"""

from responsibleai.runtime.authority_kernel import (
    BackendClaim,
    IssuanceResult,
    LocalEffectPermit,
    Phase7AAuthorityKernel,
    QueueTicket,
)
from responsibleai.runtime.dispatcher import start_phase7a_dispatcher
from responsibleai.runtime.errors import (
    Phase7ADispatcherDisabledError,
    Phase7AProductionGateClosedError,
)
from responsibleai.runtime.gate import PRODUCTION_GATE_B_OPEN, phase7a_dispatcher_flag_from_env
from responsibleai.runtime.lock_order import CANONICAL_LOCK_ORDER

__all__ = [
    "BackendClaim",
    "CANONICAL_LOCK_ORDER",
    "IssuanceResult",
    "LocalEffectPermit",
    "PRODUCTION_GATE_B_OPEN",
    "Phase7AAuthorityKernel",
    "Phase7ADispatcherDisabledError",
    "Phase7AProductionGateClosedError",
    "QueueTicket",
    "phase7a_dispatcher_flag_from_env",
    "start_phase7a_dispatcher",
]
