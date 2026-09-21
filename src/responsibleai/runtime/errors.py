# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Phase 7A runtime errors. None of these grant authority."""


class Phase7AError(Exception):
    """Base runtime error."""


class Phase7AProductionGateClosedError(Phase7AError):
    """Production Gate B is closed; dispatcher must not start."""


class Phase7ADispatcherDisabledError(Phase7AError):
    """PHASE7A_DISPATCHER_ENABLED is false."""


class AuthorityKernelError(Phase7AError):
    """Durable authority kernel refused an operation."""


class AuthorityDatabaseError(AuthorityKernelError):
    """Phase 7A authority requires PostgreSQL."""


class IdempotencyConflictError(AuthorityKernelError):
    """Same idempotency key reused with a different action digest."""


class AuthorizationIneligibleError(AuthorityKernelError):
    """Authorization is not eligible for consume or final CAS."""


class PreEffectCasRejected(AuthorityKernelError):  # noqa: N818 — frozen Phase 7A public type
    """Final pre-effect CAS lost. Attempt is FAILED_PRE_EXECUTION."""


class UncertainExternalEffectError(AuthorityKernelError):
    """External transmission outcome is unknown. Automatic replay is forbidden."""


class CrossTenantAccessError(AuthorityKernelError):
    """Request, authorization, or attempt belongs to another organization."""


class DuplicateEffectClaimError(AuthorityKernelError):
    """Physical effect was already claimed."""


class StaleWorkerError(AuthorityKernelError):
    """Lease, fence generation, or worker identity does not match."""
