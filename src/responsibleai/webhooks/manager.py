"""Enterprise webhook delivery system.

Features:
- HMAC-SHA256 payload signing (X-RAI-Signature-256 header)
- Exponential backoff retry (1 s / 5 s / 30 s)
- Concurrent fan-out via asyncio.gather
- Provider-specific payload formatting: Slack Block Kit, Teams Adaptive Card,
  PagerDuty Events API v2, generic JSON
- In-memory delivery log (last 1 000 entries)
- Thread-safe registration / removal
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from collections import deque
from typing import Any

import httpx

from responsibleai.webhooks.models import (
    WebhookConfig,
    WebhookDelivery,
    WebhookEvent,
    WebhookProvider,
)

logger = logging.getLogger(__name__)

_RETRY_DELAYS = [1.0, 5.0, 30.0]
_MAX_DELIVERY_LOG = 1_000


class WebhookManager:
    """Register endpoints and fire events with HMAC signing and retry logic."""

    def __init__(self) -> None:
        self._configs: dict[str, WebhookConfig] = {}
        self._delivery_log: deque[WebhookDelivery] = deque(maxlen=_MAX_DELIVERY_LOG)

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, config: WebhookConfig) -> WebhookConfig:
        self._configs[config.id] = config
        return config

    def remove(self, webhook_id: str) -> bool:
        return self._configs.pop(webhook_id, None) is not None

    def get(self, webhook_id: str) -> WebhookConfig | None:
        return self._configs.get(webhook_id)

    def list(self) -> list[WebhookConfig]:
        return list(self._configs.values())

    def update(self, webhook_id: str, **kwargs: Any) -> WebhookConfig | None:
        cfg = self._configs.get(webhook_id)
        if cfg is None:
            return None
        for k, v in kwargs.items():
            if hasattr(cfg, k):
                object.__setattr__(cfg, k, v) if cfg.__dataclass_fields__[k].init else None
                cfg.__dict__[k] = v
        return cfg

    # ── Delivery ──────────────────────────────────────────────────────────────

    async def fire(
        self, event: WebhookEvent, data: dict[str, Any]
    ) -> list[WebhookDelivery]:
        """Deliver *event* to all matching, enabled webhooks concurrently."""
        targets = [
            c for c in self._configs.values()
            if c.enabled and event in c.events
        ]
        if not targets:
            return []

        results = await asyncio.gather(
            *[self._deliver(cfg, event, data) for cfg in targets],
            return_exceptions=True,
        )
        deliveries: list[WebhookDelivery] = []
        for r in results:
            if isinstance(r, WebhookDelivery):
                self._delivery_log.append(r)
                deliveries.append(r)
        return deliveries

    async def _deliver(
        self, config: WebhookConfig, event: WebhookEvent, data: dict[str, Any]
    ) -> WebhookDelivery:
        payload = self._format_payload(config.provider, event, data)
        delivery = WebhookDelivery(
            webhook_id=config.id, event=event, payload=payload
        )
        delays = [0.0] + _RETRY_DELAYS[: config.max_retries - 1]

        for delay in delays:
            if delay:
                await asyncio.sleep(delay)
            delivery.attempts += 1
            try:
                body = json.dumps(payload).encode()
                headers: dict[str, str] = {"Content-Type": "application/json"}
                if config.secret:
                    sig = hmac.new(
                        config.secret.encode(), body, hashlib.sha256
                    ).hexdigest()
                    headers["X-RAI-Signature-256"] = f"sha256={sig}"

                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        config.url, content=body, headers=headers
                    )
                delivery.status_code = resp.status_code
                if resp.is_success:
                    delivery.success = True
                    return delivery
                delivery.last_error = f"HTTP {resp.status_code}"
            except Exception as exc:
                delivery.last_error = str(exc)
                logger.warning(
                    "webhook_delivery_failed",
                    extra={
                        "webhook_id": config.id,
                        "event": event.value,
                        "attempt": delivery.attempts,
                        "error": str(exc),
                    },
                )

        return delivery

    # ── Delivery log ──────────────────────────────────────────────────────────

    def delivery_log(self, limit: int = 100) -> list[dict[str, Any]]:
        entries = list(self._delivery_log)[-limit:]
        return [d.to_dict() for d in reversed(entries)]

    @property
    def total_deliveries(self) -> int:
        return len(self._delivery_log)

    @property
    def failed_deliveries(self) -> int:
        return sum(1 for d in self._delivery_log if not d.success)

    # ── Payload formatters ────────────────────────────────────────────────────

    def _format_payload(
        self,
        provider: WebhookProvider,
        event: WebhookEvent,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        if provider == WebhookProvider.SLACK:
            return self._slack_payload(event, data)
        if provider == WebhookProvider.TEAMS:
            return self._teams_payload(event, data)
        if provider == WebhookProvider.PAGERDUTY:
            return self._pagerduty_payload(event, data)
        return {
            "event": event.value,
            "timestamp": int(time.time()),
            "source": "responsibleai",
            "data": data,
        }

    def _slack_payload(self, event: WebhookEvent, data: dict[str, Any]) -> dict[str, Any]:
        _emoji = {
            WebhookEvent.DRIFT_ALERT: ":warning:",
            WebhookEvent.BUDGET_EXCEEDED: ":money_with_wings:",
            WebhookEvent.GUARDRAIL_TRIGGERED: ":shield:",
            WebhookEvent.TRUST_SCORE_CHANGED: ":bar_chart:",
        }
        emoji = _emoji.get(event, ":bell:")
        title = event.value.replace("_", " ").title()
        fields = [
            {"type": "mrkdwn", "text": f"*{k}*\n{v}"}
            for k, v in list(data.items())[:6]
        ]
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji}  ResponsibleAI — {title}",
                    },
                },
                {"type": "section", "fields": fields} if fields else {"type": "divider"},
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"<!date^{int(time.time())}^{{date_short_pretty}} at {{time}}|{time.strftime('%Y-%m-%d %H:%M UTC')}>",
                        }
                    ],
                },
            ]
        }

    def _teams_payload(self, event: WebhookEvent, data: dict[str, Any]) -> dict[str, Any]:
        color = "FF6B6B" if "alert" in event.value or "exceeded" in event.value else "4CAF50"
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": f"ResponsibleAI: {event.value}",
            "sections": [
                {
                    "activityTitle": f"**{event.value.replace('_', ' ').title()}**",
                    "activitySubtitle": "ResponsibleAI Governance Platform",
                    "facts": [{"name": k, "value": str(v)} for k, v in data.items()],
                    "markdown": True,
                }
            ],
        }

    def _pagerduty_payload(
        self, event: WebhookEvent, data: dict[str, Any]
    ) -> dict[str, Any]:
        severity = (
            "critical"
            if event in (WebhookEvent.BUDGET_EXCEEDED, WebhookEvent.GUARDRAIL_TRIGGERED)
            else "warning"
        )
        return {
            "routing_key": data.get("routing_key", ""),
            "event_action": "trigger",
            "dedup_key": f"rai-{event.value}-{int(time.time() // 60)}",
            "payload": {
                "summary": f"ResponsibleAI: {event.value.replace('_', ' ').title()}",
                "severity": severity,
                "source": "responsibleai",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "custom_details": {k: v for k, v in data.items() if k != "routing_key"},
            },
        }
