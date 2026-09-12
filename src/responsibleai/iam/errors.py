# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise IAM Domain Errors & Exceptions."""

from __future__ import annotations


class IAMError(Exception):
    """Base exception for all Enterprise IAM failures."""


class PrivilegedAccessDeniedError(IAMError):
    """Raised when an operation fails authorization at the privileged surface guard."""


class StepUpRequiredError(IAMError):
    """Raised when an operation requires fresh step-up reauthentication."""

    def __init__(self, message: str, required_nonce: str | None = None, max_age_seconds: int = 900) -> None:
        super().__init__(message)
        self.required_nonce = required_nonce
        self.max_age_seconds = max_age_seconds


class StepUpVerificationFailedError(IAMError):
    """Raised when a provided step-up proof is invalid, expired, or replayed."""


class FourEyesRequiredError(IAMError):
    """Raised when an action requires independent dual-custody approval."""

    def __init__(self, message: str, approval_request_id: str | None = None) -> None:
        super().__init__(message)
        self.approval_request_id = approval_request_id


class SelfApprovalBlockedError(IAMError):
    """Raised when a requester attempts to approve their own privileged request."""


class JitGrantInvalidError(IAMError):
    """Raised when a JIT grant is inactive, expired, or bound to another capability."""


class BreakGlassInvalidError(IAMError):
    """Raised when an emergency break-glass token is invalid, expired, or missing an incident ID."""


class SovereignRecoveryError(IAMError):
    """Raised when a sovereign customer root recovery fails cryptographic verification."""


class CrossTenantEscalationError(IAMError):
    """Raised when an identity attempts to invoke privileged operations across tenant boundaries."""


class OperatorBackdoorAttemptError(IAMError):
    """Raised when a platform operator attempts to exercise unauthorized tenant root power."""


class SecurityEpochExpiredError(IAMError):
    """Raised when a credential or session predates the current security revocation epoch."""
