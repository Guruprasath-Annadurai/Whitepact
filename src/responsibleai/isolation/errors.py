# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Exception hierarchy for the WhitePact Independent Runtime Isolation Plane."""

from __future__ import annotations


class IsolationError(Exception):
    """Base exception for all runtime isolation failures."""


class IsolationBackendUnavailableError(IsolationError):
    """Raised when the configured isolation backend cannot be initialized
    or reached (e.g. Docker daemon is down). Always fails closed."""


class IsolationRuntimeUnavailableError(IsolationBackendUnavailableError):
    """Executor proved runtime refusal before durable nonce admission.

    Only the executor's pre-admission boundary may emit this classification.
    It does not restore a consumed approval or authorize a retry.
    """


class IsolationExecutionUncertainError(IsolationError):
    """Isolation failed after admission; side effects require reconciliation."""


class IsolationPolicyViolationError(IsolationError):
    """Raised when an execution request violates isolation constraints
    (e.g., untrusted workload attempting unauthorized network egress)."""


class ResourceLimitExceededError(IsolationError):
    """Raised when an isolated execution exceeds allocated CPU, memory, or PID limits."""


class IsolationTimeoutExceededError(IsolationError):
    """Raised when an execution exceeds the maximum wall-clock timeout."""


class InvalidBackendModeError(IsolationError):
    """Raised when an invalid or insecure backend mode is requested
    (e.g. attempting to use LOCAL_DEV in production)."""


class FilesystemEscapeError(IsolationError):
    """Raised when an isolated task attempts to access paths outside its workspace."""


class IsolationFilesystemPermissionError(IsolationError):
    """Raised when the host cannot grant container access without weakening isolation."""
