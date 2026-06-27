# Webhooks

ResponsibleAI can push governance events to external systems (Slack, Teams, PagerDuty, or any HTTP endpoint) when thresholds fire.

---

## Supported events

| Event | Fired when |
|---|---|
| `drift_alert` | Trust score drops ≥ `RAI_ALERT_THRESHOLD` points |
| `budget_exceeded` | Monthly spend exceeds `RAI_MONTHLY_BUDGET_USD` |
| `guardrail_triggered` | PII or toxic content blocked |
| `trust_score_changed` | New trust score recorded |
| `eval_completed` | Evaluation run finished |

---

## Register a webhook

```bash
curl -X POST http://localhost:8765/api/webhooks \
  -H "Authorization: Bearer your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ops-alerts",
    "url": "https://hooks.slack.com/services/...",
    "events": ["drift_alert", "budget_exceeded"],
    "provider": "slack",
    "secret": "hmac-secret-for-verification",
    "max_retries": 5
  }'
```

**Providers:** `slack` (Block Kit), `teams` (Adaptive Card), `pagerduty` (Events API v2), `generic` (JSON).

---

## Payload format

### Generic JSON

```json
{
  "event": "drift_alert",
  "timestamp": 1719360000,
  "source": "responsibleai",
  "data": {
    "model": "gpt-4o",
    "provider": "openai",
    "delta": -7.3,
    "severity": "HIGH"
  }
}
```

### Slack Block Kit

```json
{
  "blocks": [
    { "type": "header", "text": { "type": "plain_text", "text": "⚠️  ResponsibleAI — Drift Alert" } },
    { "type": "section", "fields": [...] },
    { "type": "context", "elements": [...] }
  ]
}
```

---

## Payload verification

All deliveries include an HMAC-SHA256 signature:

```
X-RAI-Signature-256: sha256=<hex>
```

Verify in your endpoint:

```python
import hashlib, hmac

def verify_signature(secret: str, body: bytes, header: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)
```

---

## Retry behaviour

Deliveries are persisted to the `webhook_deliveries` table. If delivery fails, the background retry worker picks it up and retries on the schedule below:

| Attempt | Delay after previous failure |
|---|---|
| 1 | Immediate |
| 2 | 1 second |
| 3 | 5 seconds |
| 4 | 30 seconds |
| 5 | 2 minutes |
| 6+ | 10 minutes (max) |

**Restarts are safe:** pending retries survive server restarts. The worker polls the DB every 30 seconds on startup.

Status machine: `pending → retrying → delivered | failed`

---

## Delivery log

```bash
# View recent deliveries
curl http://localhost:8765/api/webhooks/deliveries \
  -H "Authorization: Bearer your-key"
```

```json
[
  {
    "id": "uuid",
    "webhook_id": "uuid",
    "event": "drift_alert",
    "status": "delivered",
    "attempts": 1,
    "status_code": 200,
    "delivered_at": "2026-06-27T14:23:01+00:00"
  }
]
```

---

## Test a webhook

```bash
curl -X POST http://localhost:8765/api/webhooks/{webhook_id}/test \
  -H "Authorization: Bearer your-key"
```

Fires a `test.ping` event to confirm the endpoint is reachable.

---

## PagerDuty integration

```json
{
  "name": "on-call-escalation",
  "url": "https://events.pagerduty.com/v2/enqueue",
  "events": ["drift_alert", "guardrail_triggered"],
  "provider": "pagerduty",
  "secret": "your-pagerduty-integration-key"
}
```

The `routing_key` must be in the event `data.routing_key` field. Severity mapping: `budget_exceeded` and `guardrail_triggered` → critical; everything else → warning.
