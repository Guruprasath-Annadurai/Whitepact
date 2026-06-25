"""Webhook domain models."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WebhookEvent(str, Enum):
    DRIFT_ALERT = "drift_alert"
    BUDGET_EXCEEDED = "budget_exceeded"
    GUARDRAIL_TRIGGERED = "guardrail_triggered"
    TRUST_SCORE_CHANGED = "trust_score_changed"


class WebhookProvider(str, Enum):
    SLACK = "slack"
    TEAMS = "teams"
    PAGERDUTY = "pagerduty"
    GENERIC = "generic"


@dataclass
class WebhookConfig:
    url: str
    events: list[WebhookEvent]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    provider: WebhookProvider = WebhookProvider.GENERIC
    secret: str = ""
    enabled: bool = True
    max_retries: int = 3
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "events": [e.value for e in self.events],
            "provider": self.provider.value,
            "enabled": self.enabled,
            "max_retries": self.max_retries,
            "description": self.description,
            "has_secret": bool(self.secret),
        }


@dataclass
class WebhookDelivery:
    webhook_id: str
    event: WebhookEvent
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status_code: int | None = None
    success: bool = False
    attempts: int = 0
    last_error: str | None = None
    delivered_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "webhook_id": self.webhook_id,
            "event": self.event.value,
            "status_code": self.status_code,
            "success": self.success,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "delivered_at": self.delivered_at,
        }
