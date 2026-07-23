"""Enterprise webhook delivery system.

Features:
- HMAC-SHA256 payload signing (X-RAI-Signature-256 header)
- Exponential backoff retry (1 s / 5 s / 30 s / 2 min / 10 min)
- Concurrent fan-out via asyncio.gather
- Provider-specific payload formatting: Slack Block Kit, Teams Adaptive Card,
  PagerDuty Events API v2, generic JSON
- DB-persisted delivery log with retry recovery across server restarts
- In-memory fallback when no DB is configured (test / dev)
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from collections import deque
from typing import TYPE_CHECKING, Any

import httpx

from responsibleai.webhooks.models import (
    WebhookConfig,
    WebhookDelivery,
    WebhookEvent,
    WebhookProvider,
)

if TYPE_CHECKING:
    from responsibleai.db.webhook_repository import (
        WebhookConfigRepository,
        WebhookDeliveryRepository,
    )

logger = logging.getLogger(__name__)

_RETRY_DELAYS = [1.0, 5.0, 30.0, 120.0, 600.0]
_MAX_DELIVERY_LOG = 1_000
_RETRY_POLL_INTERVAL = 30.0


class WebhookManager:
    """Register endpoints and fire events with HMAC signing and persistent retry logic."""

    def __init__(self) -> None:
        self._configs: dict[str, WebhookConfig] = {}
        self._delivery_log: deque[WebhookDelivery] = deque(maxlen=_MAX_DELIVERY_LOG)
        self._repo: WebhookDeliveryRepository | None = None
        self._config_repo: WebhookConfigRepository | None = None
        self._retry_task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event = asyncio.Event()

    def set_repository(self, repo: WebhookDeliveryRepository) -> None:
        """Wire up the DB repository for persistent delivery log and retry queue."""
        self._repo = repo

    def set_config_repository(self, repo: WebhookConfigRepository) -> None:
        """Wire up the DB repository for persistent webhook registrations."""
        self._config_repo = repo

    async def load_configs(self) -> int:
        """Repopulate the in-memory registry from the DB. Call once at
        startup, after set_config_repository(). Returns the count loaded."""
        if self._config_repo is None:
            return 0
        configs = await self._config_repo.list_all()
        for cfg in configs:
            self._configs[cfg.id] = cfg
        return len(configs)

    def start_retry_worker(self) -> None:
        """Launch background retry worker (call after lifespan startup + repo attached)."""
        if self._repo is not None and self._retry_task is None:
            self._stop_event.clear()
            self._retry_task = asyncio.create_task(self._retry_worker())

    def stop_retry_worker(self) -> None:
        """Signal the background worker to stop."""
        self._stop_event.set()
        if self._retry_task is not None:
            self._retry_task.cancel()
            self._retry_task = None

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, config: WebhookConfig) -> WebhookConfig:
        """In-memory only. Use register_and_persist() from request handlers
        so a registered webhook survives a restart."""
        self._configs[config.id] = config
        return config

    def remove(self, webhook_id: str) -> bool:
        """In-memory only. Use remove_and_persist() from request handlers."""
        return self._configs.pop(webhook_id, None) is not None

    async def register_and_persist(self, config: WebhookConfig) -> WebhookConfig:
        self.register(config)
        if self._config_repo is not None:
            await self._config_repo.create(config)
        return config

    async def remove_and_persist(self, webhook_id: str, org_id: str | None = None) -> bool:
        """Remove a webhook. If org_id is given, only removes a config owned
        by that org (returns False otherwise) — enforces tenant isolation."""
        cfg = self._configs.get(webhook_id)
        if cfg is None:
            return False
        if org_id is not None and cfg.org_id != org_id:
            return False
        removed_locally = self.remove(webhook_id)
        if self._config_repo is not None:
            await self._config_repo.delete(webhook_id, org_id=org_id)
        return removed_locally

    def get(self, webhook_id: str) -> WebhookConfig | None:
        return self._configs.get(webhook_id)

    def list_webhooks(self, org_id: str | None = None) -> list[WebhookConfig]:
        """List registered webhooks. Pass org_id to scope to one tenant —
        omit only for legacy/super-admin cross-org visibility."""
        if org_id is None:
            return list(self._configs.values())
        return [c for c in self._configs.values() if c.org_id == org_id]

    def update(self, webhook_id: str, **kwargs: Any) -> WebhookConfig | None:
        cfg = self._configs.get(webhook_id)
        if cfg is None:
            return None
        for k, v in kwargs.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
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
        self,
        config: WebhookConfig,
        event: WebhookEvent,
        data: dict[str, Any],
        delivery_id: str | None = None,
        start_attempt: int = 0,
    ) -> WebhookDelivery:
        payload = self._format_payload(config.provider, event, data)
        delivery = WebhookDelivery(
            webhook_id=config.id, event=event, payload=payload,
        )
        if delivery_id:
            delivery.id = delivery_id

        if self._repo:
            try:
                await self._repo.create(
                    delivery_id=delivery.id,
                    webhook_id=config.id,
                    event=event.value,
                    payload=payload,
                    max_retries=config.max_retries,
                )
            except Exception:
                pass  # degraded — continue without persistence

        delays = [0.0] + _RETRY_DELAYS[: config.max_retries - 1]
        for i, delay in enumerate(delays):
            if i < start_attempt:
                continue
            if delay:
                await asyncio.sleep(delay)
            delivery.attempts += 1
            status_code: int | None = None
            error: str | None = None
            success = False
            try:
                body = json.dumps(payload).encode()
                headers: dict[str, str] = {"Content-Type": "application/json"}
                if config.secret:
                    sig = hmac.new(
                        config.secret.encode(), body, hashlib.sha256
                    ).hexdigest()
                    headers["X-RAI-Signature-256"] = f"sha256={sig}"

                async with httpx.AsyncClient(timeout=10.0) as http:
                    resp = await http.post(config.url, content=body, headers=headers)
                status_code = resp.status_code
                if resp.is_success:
                    delivery.status_code = status_code
                    delivery.success = True
                    success = True
                else:
                    error = f"HTTP {resp.status_code}"
                    delivery.last_error = error
            except Exception as exc:
                error = str(exc)
                delivery.last_error = error
                logger.warning(
                    "webhook_delivery_failed webhook_id=%s event=%s attempt=%d error=%s",
                    config.id, event.value, delivery.attempts, exc,
                )

            if self._repo:
                try:
                    await self._repo.record_attempt(
                        delivery.id, delivery.attempts, status_code, error, success
                    )
                except Exception:
                    pass

            if success:
                return delivery

        return delivery

    async def _retry_worker(self) -> None:
        """Background task: pick up pending DB retries and re-deliver them."""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(_RETRY_POLL_INTERVAL)
                if self._repo is None:
                    continue
                pending = await self._repo.pending_retries()
                for row in pending:
                    cfg = self._configs.get(row["webhook_id"])
                    if cfg is None:
                        continue
                    try:
                        event = WebhookEvent(row["event"])
                    except ValueError:
                        continue
                    asyncio.create_task(
                        self._deliver(
                            cfg, event, row["payload"],
                            delivery_id=row["id"],
                            start_attempt=row["attempts"],
                        )
                    )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("webhook_retry_worker_error: %s", exc)

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
