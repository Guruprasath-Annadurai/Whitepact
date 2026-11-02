# MCP Server

The ResponsibleAI MCP server exposes governance capabilities as tools and resources directly inside Claude Code. Every AI call can be automatically governed — trust scoring, guardrails, compliance, and audit logging — without code changes.

---

## Setup

```bash
pip install "rai-governance-platform[mcp]"
```

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "responsibleai": {
      "command": "responsibleai-mcp",
      "env": {
        "RAI_API_URL": "http://localhost:8765",
        "RAI_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

Or via Claude Code settings `/mcp` panel.

---

## Architecture

The MCP server runs as a separate stdio process. Computation tools run in-process (no REST server required). Data-query tools call the REST API.

```
Claude Code ──stdio──► responsibleai-mcp
                             │
              ┌──────────────┴──────────────┐
              │  In-process (no network)    │  REST call
              │  rai_scan                   │
              │  rai_trust_score            │──► http://localhost:8765
              │  rai_compliance             │    rai_cost_estimate
              │  rai_hallucination          │    rai_health
              │  rai_redteam_payloads       │
              │  rai_redteam_analyze        │
              │  rai_compare_models         │
              │  rai_audit_summary          │
              └─────────────────────────────┘
```

---

## Tools

### `rai_scan`

Scan text for PII and harmful content.

```json
{
  "text": "Call me at 555-123-4567 or user@company.com",
  "redact": true
}
```

Response:
```json
{
  "blocked": true,
  "pii_count": 2,
  "pii_categories": ["phone", "email"],
  "redacted_text": "Call me at [PHONE] or [EMAIL]",
  "toxicity_findings": []
}
```

---

### `rai_trust_score`

Compute a 6-dimension AI Trust Score.

```json
{
  "fairness": 0.80,
  "privacy": 0.85,
  "security": 0.82,
  "robustness": 0.78,
  "compliance": 0.90,
  "authenticity": 0.88
}
```

Response:
```json
{
  "trust_score": 83.65,
  "grade": "B",
  "risk_level": "LOW",
  "dimensions": {
    "fairness": 80.0,
    "privacy": 85.0,
    "security": 82.0,
    "robustness": 78.0,
    "compliance": 90.0,
    "authenticity": 88.0
  }
}
```

---

### `rai_compliance`

Evaluate against NIST AI RMF, EU AI Act, or ISO 42001.

```json
{
  "fairness_score": 0.80,
  "privacy_score": 0.85,
  "security_score": 0.82,
  "robustness_score": 0.78,
  "compliance_maturity": 0.90,
  "use_case": "credit_scoring",
  "framework": "EU_AI_ACT"
}
```

---

### `rai_hallucination`

Score factual reliability via self-consistency analysis.

```json
{
  "text": "AI will replace all human jobs by 2025.",
  "candidates": [
    "AI will automate some repetitive tasks.",
    "AI creates new job categories."
  ]
}
```

---

### `rai_redteam_payloads`

Get the full adversarial payload library.

```json
{ "category": "prompt_injection" }
```

Returns all payloads in that category with severity and CWE ID.

---

### `rai_redteam_analyze`

Analyze model responses against known vulnerability patterns.

```json
{
  "responses": [
    { "payload": "Ignore previous instructions...", "response": "Sure! Here's how to..." }
  ]
}
```

---

### `rai_compare_models`

Compare two models across all 6 trust dimensions.

```json
{
  "model_a": { "name": "gpt-4o", "fairness": 0.80, ... },
  "model_b": { "name": "claude-opus-4", "fairness": 0.88, ... }
}
```

---

### `rai_cost_estimate`

Get token cost estimate for a model (calls REST API for live pricing).

```json
{ "model": "gpt-4o", "input_tokens": 1000, "output_tokens": 500 }
```

---

### `rai_audit_summary`

Get audit log summary — top endpoints, error rate, latency.

```json
{ "days": 7 }
```

---

### `rai_health`

Check platform health.

```json
{}
```

---

## Resources

| URI | Description |
|---|---|
| `rai://health` | Platform health — DB, auth, OTEL, version |
| `rai://models/catalog` | All supported models with pricing |
| `rai://compliance/frameworks` | NIST AI RMF, EU AI Act, ISO 42001 controls |
| `rai://redteam/categories` | Attack vector taxonomy |
| `rai://trust/dimensions` | 6 trust dimensions with weights and guidance |

Access resources:

```
In Claude Code, resources appear in the @ picker:
  @responsibleai:rai://models/catalog
```

---

## Environment variables for MCP

| Variable | Default | Description |
|---|---|---|
| `RAI_API_URL` | `http://localhost:8765` | URL of the REST dashboard |
| `RAI_API_KEY` | *(empty)* | Bearer token for authenticated calls |

If the REST API is not running, computation tools still work (they run in-process). Only data-retrieval calls fail.
