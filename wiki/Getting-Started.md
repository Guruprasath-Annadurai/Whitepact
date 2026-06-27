# Getting Started

## Requirements

- Python 3.11 or 3.12
- pip 23+

---

## Install

```bash
# Governance platform + REST API (minimum)
pip install "rai-governance-platform[dashboard]"

# Add PostgreSQL driver
pip install "rai-governance-platform[dashboard,postgres]"

# Add Redis (distributed rate limiting)
pip install "rai-governance-platform[dashboard,redis]"

# Add OpenTelemetry
pip install "rai-governance-platform[dashboard,telemetry]"

# Add LLM providers (for bias evaluation)
pip install "rai-governance-platform[dashboard,openai,anthropic]"

# Everything
pip install "rai-governance-platform[all]"
```

---

## 5-minute quickstart

### 1. Start the dashboard

```bash
# No auth, SQLite in-memory (dev mode)
RAI_AUTH_ENABLED=false \
uvicorn responsibleai.dashboard.app:app --port 8765
```

Open [http://localhost:8765](http://localhost:8765) — live dark-mode dashboard.  
API docs: [http://localhost:8765/api/docs](http://localhost:8765/api/docs)

### 2. Evaluate a model

```bash
curl -s -X POST http://localhost:8765/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "gpt-4o",
    "provider": "openai",
    "fairness": 0.80,
    "privacy": 0.85,
    "security": 0.82,
    "robustness": 0.78,
    "compliance": 0.90,
    "authenticity": 0.88
  }' | python3 -m json.tool
```

### 3. Scan for PII

```bash
curl -s -X POST http://localhost:8765/api/scan \
  -H "Content-Type: application/json" \
  -d '{"text": "Call me at 555-123-4567 or user@company.com. My SSN is 123-45-6789."}' \
  | python3 -m json.tool
```

### 4. Check compliance

```bash
curl -s http://localhost:8765/api/health | python3 -m json.tool
```

---

## Production setup

```bash
# Generate an API key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# → example: abc123xyz...

# Start with auth and persistent SQLite
RAI_API_KEYS=abc123xyz \
RAI_DB_PATH=/var/lib/rai/governance.db \
uvicorn responsibleai.dashboard.app:app \
  --host 0.0.0.0 --port 8765 --workers 4
```

Run Alembic before first production start:

```bash
RAI_DB_PATH=/var/lib/rai/governance.db alembic upgrade head
```

---

## Python SDK

```python
from responsibleai import (
    TrustScoreEngine,
    ComplianceEngine,
    GuardrailsEngine,
    HallucinationDetector,
    RedTeamSimulator,
    CostTracker,
    ModelRouter,
    TrustDriftMonitor,
    PassportGenerator,
)

engine = TrustScoreEngine()
score = engine.compute(
    fairness=0.80, privacy=0.85, security=0.82,
    robustness=0.78, compliance=0.90, authenticity=0.88,
)
print(f"{score.overall:.1f}/100  Grade: {score.grade}  Risk: {score.risk_level}")
```

---

## MCP Server (Claude Code)

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
        "RAI_API_KEY": "your-key"
      }
    }
  }
}
```

Now Claude Code has 10 governance tools available. See [MCP Server](MCP-Server) for full reference.

---

## Docker

```bash
git clone https://github.com/Guruprasath-Annadurai/ResponsibleAi.git
cd ResponsibleAi
cp .env.example .env
# Edit .env — set RAI_API_KEYS
docker compose up -d
```
