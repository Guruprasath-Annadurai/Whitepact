# Five-minute quickstart (stranger path)

Goal: **zero-context → first successful governed action** on a clean machine.

This guide uses only commands and APIs that exist in this repository. If a step
cannot be completed without founder-only credentials, it is called out explicitly.

## Prerequisites

- Python **3.11+**
- Git
- Optional: Docker 24+ and Docker Compose v2 for the container path

## Path A — Fastest (local Python, ~2 minutes)

### 1. Clone and install

```bash
git clone https://github.com/Guruprasath-Annadurai/Whitepact.git
cd Whitepact
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dashboard]"
```

### 2. Run the minimal authority demo

```bash
python examples/quickstart_stranger_authority.py
```

You should see:

1. A delegated **authority context** for agent `quickstart-agent`
2. **ALLOW** for `payment.execute` within limits
3. **DENY** for an ungranted action type
4. An **evidence** record with `chain_valid=True`
5. **Revocation** clearing effective authority (`get_effective_authority() → None`)

**Limitation (documented honestly):** `WhitePactRuntimeGateway.evaluate()` trusts the
`AuthorityContext` you pass in. Production HTTP/MCP paths **reload** delegations each
request; the script shows both revocation and why stale contexts must not be reused.

### 3. Deep dive (optional, ~5 more minutes)

```bash
python examples/08_whitepact_enterprise_scenario.py
```

End-to-end org ceiling, attenuated delegation, approvals, workflow denial, evidence bundle.

---

## Path B — Dashboard + trust evaluation (README default)

This path proves the **dashboard** and **trust scoring** APIs. It does **not** by
itself walk the full delegation graph; use Path A for authority allow/deny/revoke.

```bash
pip install "rai-governance-platform[dashboard]"
uvicorn responsibleai.dashboard.app:app --host 127.0.0.1 --port 8765
```

Health:

```bash
curl -fsS http://127.0.0.1:8765/api/health
```

Trust evaluation (no LLM key — you supply dimension scores):

```bash
curl -fsS -X POST http://127.0.0.1:8765/api/evaluate \
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
  }'
```

With `RAI_AUTH_ENABLED=true` (default in `.env.example`), protected routes need
`Authorization: Bearer <api-key>`. For local smoke tests you may set
`RAI_AUTH_ENABLED=false` in `.env` **development only**.

Governed HTTP tool calls (org-scoped key required) use
`POST /api/governance/tools/call` — see [HTTP examples](examples/http_governance.md).

---

## Path C — Docker Compose

```bash
cp .env.example .env
# Edit RAI_API_KEYS and other values; never commit .env
docker compose up --build -d
curl -fsS http://127.0.0.1:8765/api/health
```

Data persists in the `rai-data` volume (`RAI_DB_PATH=/data/responsibleai.db`).

Stop and remove containers (keep volume):

```bash
docker compose down
```

---

## Path D — Helm (Kubernetes)

See [Installation](installation.md#helm). Validate charts without deploying:

```bash
helm lint helm/rai-governance
helm template smoke helm/rai-governance --set dashboard.image.tag=1.3.1
```

---

## MCP (30 production tools)

Self-hosted stdio (no remote API key):

```bash
pip install "rai-governance-platform[dashboard,mcp]"
whitepact-mcp   # alias: responsibleai-mcp
```

Remote Streamable HTTP and client wiring: [MCP quickstart](mcp-quickstart.md).

---

## Clean-room verification

```bash
bash scripts/launch-readiness/clean_room_smoke.sh
```

---

## Where to go next

- [START_HERE.md](START_HERE.md) — full documentation map
- [Troubleshooting](troubleshooting.md)
- [Launch readiness audit](launch-readiness/WHITEPACT_STRANGER_ONBOARDING_AUDIT.md)
