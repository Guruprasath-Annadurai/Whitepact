# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Sovereign read/simulation errors — non-authoritative, fail-closed."""

from __future__ import annotations


class SovereignError(Exception):
    """Base error for Sovereign service layer. Never grants authority."""


class SovereignCapabilityError(SovereignError):
    """Requested capability is unavailable or unsupported."""


class SovereignTenantIsolationError(SovereignError):
    """Cross-organization access denied without disclosing foreign data."""


class SovereignValidationError(SovereignError):
    """Invalid manifest, protocol, or request shape."""


class SovereignGraphBudgetError(SovereignError):
    """Graph traversal exceeded depth, node, or time budget."""
