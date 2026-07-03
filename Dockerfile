FROM python:3.12-slim AS builder

WORKDIR /build
RUN pip install --upgrade pip build
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN python -m build --wheel --outdir /dist


FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="ResponsibleAI Governance Platform"
LABEL org.opencontainers.image.description="Enterprise AI Governance — Trust Scoring, Compliance, Cost Intelligence"
LABEL org.opencontainers.image.version="1.1.0"
LABEL org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RAI_HOST=0.0.0.0 \
    RAI_PORT=8765 \
    RAI_LOG_JSON=true \
    RAI_DB_PATH=/data/responsibleai.db

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/sh --create-home appuser

RUN mkdir -p /data && chown appuser:appgroup /data

WORKDIR /app
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl \
    "fastapi>=0.110" "uvicorn[standard]>=0.29" \
    "slowapi>=0.1" "pydantic-settings>=2.0" "structlog>=24.0" "python-dotenv>=1.0"

COPY src/responsibleai/dashboard/static/ /app/static/

USER appuser

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8765/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d['status'] in ('healthy','degraded') else 1)"

CMD ["sh", "-c", "uvicorn responsibleai.dashboard.app:app \
    --host ${RAI_HOST} \
    --port ${RAI_PORT} \
    --workers ${RAI_WORKERS:-1} \
    --no-access-log"]
