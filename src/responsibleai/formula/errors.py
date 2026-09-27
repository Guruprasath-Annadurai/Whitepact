# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# ruff: noqa: N818 — Gate 2 spec requires these exception type names.
"""Structured Formula domain errors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FormulaDomainError(Exception):
    message: str
    code: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class InvalidGraph(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="INVALID_GRAPH")


class CrossTenantReference(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="CROSS_TENANT_REFERENCE")


class InvalidGrant(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="INVALID_GRANT")


class AuthorityExpansion(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="AUTHORITY_EXPANSION")


class InvalidDelegation(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="INVALID_DELEGATION")


class ExpiredGrant(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="EXPIRED_GRANT")


class RevokedGrant(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="REVOKED_GRANT")


class ConsumedGrant(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="CONSUMED_GRANT")


class VersionMismatch(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="VERSION_MISMATCH")


class InvalidTrace(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="INVALID_TRACE")


class UnknownNodeKind(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="UNKNOWN_NODE_KIND")


class InvalidCapability(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="INVALID_CAPABILITY")


class InvalidCapabilityRule(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="INVALID_CAPABILITY_RULE")


class CapabilityBudgetExceeded(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="CAPABILITY_BUDGET_EXCEEDED")


class CapabilityTenantMismatch(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="CAPABILITY_TENANT_MISMATCH")


class InvalidCapabilityDerivation(FormulaDomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="INVALID_CAPABILITY_DERIVATION")
