"""Explicit error and denial semantics for Community Core."""

from __future__ import annotations

from typing import Any


class WhitePactCommunityError(Exception):
    """Base error for all Community Core failures."""

    exit_code: int = 1


class ConfigurationError(WhitePactCommunityError):
    """Malformed or unsafe local configuration."""

    exit_code = 2


class GovernanceDenied(WhitePactCommunityError):
    """A governed operation was explicitly denied (or quarantined)."""

    exit_code = 3

    def __init__(self, message: str, *, decision: str, reason_codes: list[str] | None = None) -> None:
        super().__init__(message)
        self.decision = decision
        self.reason_codes = list(reason_codes or [])


class CommunityCapabilityUnavailable(WhitePactCommunityError):
    """Requested capability requires enterprise/private infrastructure.

    Never reported as a successful simulation.
    """

    exit_code = 4

    def __init__(self, capability: str, detail: str | None = None) -> None:
        msg = f"Community Core does not provide capability {capability!r}"
        if detail:
            msg = f"{msg}: {detail}"
        super().__init__(msg)
        self.capability = capability
        self.detail = detail


class AuthorizationError(WhitePactCommunityError):
    """Expired, revoked, replayed, or mismatched execution authorization."""

    exit_code = 5


def error_payload(exc: BaseException) -> dict[str, Any]:
    """Structured error dict suitable for CLI JSON / MCP tool results."""
    payload: dict[str, Any] = {
        "error": type(exc).__name__,
        "message": str(exc),
    }
    if isinstance(exc, GovernanceDenied):
        payload["decision"] = exc.decision
        payload["reason_codes"] = exc.reason_codes
        payload["exit_code"] = exc.exit_code
    elif isinstance(exc, CommunityCapabilityUnavailable):
        payload["capability"] = exc.capability
        payload["exit_code"] = exc.exit_code
    elif isinstance(exc, WhitePactCommunityError):
        payload["exit_code"] = exc.exit_code
    return payload
