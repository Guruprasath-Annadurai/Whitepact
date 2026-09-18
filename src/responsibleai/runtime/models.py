# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Phase 7A durable state enumerations. Redis is never represented here."""

from __future__ import annotations

from enum import Enum


class RequestLifecycle(str, Enum):
    RECORDED = "RECORDED"


class AuthorizationStatus(str, Enum):
    ISSUED = "ISSUED"
    CONSUMED = "CONSUMED"


class AttemptState(str, Enum):
    PENDING = "PENDING"
    LEASED = "LEASED"
    ADMITTED = "ADMITTED"
    BACKEND_STARTING = "BACKEND_STARTING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED_PRE_EXECUTION = "FAILED_PRE_EXECUTION"
    FAILED = "FAILED"
    UNCERTAIN = "UNCERTAIN"


class EffectState(str, Enum):
    NO_EFFECT = "NO_EFFECT"
    EFFECT_STARTING = "EFFECT_STARTING"
    EFFECT_TRANSMITTING = "EFFECT_TRANSMITTING"
    EFFECT_CONFIRMED = "EFFECT_CONFIRMED"
    EFFECT_FAILED = "EFFECT_FAILED"
    EFFECT_UNCERTAIN = "EFFECT_UNCERTAIN"


class LeaseStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    FAILED = "FAILED"


class OutboxStatus(str, Enum):
    PENDING = "PENDING"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class PreEffectDecision(str, Enum):
    ALLOW_EFFECT = "ALLOW_EFFECT"
    DENY_FAILED_PRE_EXECUTION = "DENY_FAILED_PRE_EXECUTION"
