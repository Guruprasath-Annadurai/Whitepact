# Roadmap

## Shipped

| Version | Highlights |
|---|---|
| v0.1 | BiasBuster core: gender probe, 4 LLM providers, CLI, CI integration |
| v0.2 | Racial / age / religious / occupational probes, HTML reporter, PrivacyLabel federated DP |
| v0.3 | Cultural bias, intersectional analysis, DeepfakeDetector ensemble |
| v0.4 | Cost Intelligence (CostTracker, ModelRouter, 16-model pricing), Trust Drift Monitor |
| v0.5 | Governance Dashboard (FastAPI), Trust Score, AI Passport, Guardrails, Hallucination Detector, Compliance Engine, Red Team Simulator, Docker, SLA |
| v0.6 | Async PostgreSQL (SQLAlchemy), Redis rate limiting, OpenTelemetry APM, LLM integration tests |
| v1.0 | WebSocket real-time drift alerts, Prometheus /metrics endpoint, multi-tenant RBAC, org management API, AI Passport export, webhook delivery system |
| v1.1 | **MCP Server** (10 tools, 5 resources), audit log API, red team API, billing API, **Alembic migrations**, **per-org rate limiting**, **DB-persisted webhook retry queue**, 942 tests |

---

## Planned

### v1.2 — Streaming governance

- Real-time token-stream scanning (StreamingScanner fully integrated into the API)
- Per-token PII redaction via SSE/WebSocket endpoint
- Streaming cost accumulation with mid-stream budget alerts

### v1.3 — Advanced observability

- Prometheus push gateway support
- Grafana dashboard provisioned in Helm chart
- Distributed tracing propagation across MCP → dashboard calls
- Anomaly detection on cost patterns (spike alerts)

### v1.4 — SDK hardening

- Python SDK with typed models, retry logic, async/sync interfaces (`sdk/python/`)
- TypeScript SDK for Node.js integrations (`sdk/typescript/`)
- Go SDK for high-throughput sidecar deployments (`sdk/go/`)

### v2.0 — ML-backed governance

- Actual hallucination detection using a secondary verifier model (vs. current TF-IDF heuristic)
- Real-time bias detection on model output streams (vs. offline probe runs)
- ML-based drift prediction — forecast degradation before it occurs
- SOC 2 audit trail export (JSON-L with cryptographic chaining)

---

## Explicitly out of scope

- **Real-time model interception** — we score, we don't proxy. Model calls go directly to the provider.
- **Model fine-tuning** — governance, not training.
- **Data labeling** — PrivacyLabel handles federated privacy, not general annotation.
