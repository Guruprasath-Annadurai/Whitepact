FROM python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17 AS builder

WORKDIR /build
RUN pip install --no-cache-dir build==1.5.0
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN python -m build --wheel --outdir /dist


FROM python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17 AS runtime

LABEL org.opencontainers.image.title="ResponsibleAI Governance Platform"
LABEL org.opencontainers.image.description="Enterprise AI Governance — Trust Scoring, Compliance, Cost Intelligence"
LABEL org.opencontainers.image.version="1.2.4rc1"
LABEL org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WHITEPACT_HOST=0.0.0.0 \
    WHITEPACT_PORT=8765 \
    WHITEPACT_LOG_JSON=true \
    WHITEPACT_DB_PATH=/data/responsibleai.db

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/sh --create-home appuser

RUN mkdir -p /data && chown appuser:appgroup /data

WORKDIR /app
COPY --from=builder /dist/*.whl /tmp/
COPY requirements-production.lock /tmp/requirements-production.lock
# Install the hash-locked production closure generated from uv.lock, then
# install the candidate wheel without allowing pip to re-resolve dependencies.
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements-production.lock && \
    pip install --no-cache-dir --no-deps /tmp/*.whl

COPY src/responsibleai/dashboard/static/ /app/static/
COPY alembic.ini ./
COPY migrations/ ./migrations/

USER appuser

EXPOSE 8765 8766

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8765/api/live

CMD ["sh", "-c", "uvicorn responsibleai.dashboard.app:app \
    --host ${WHITEPACT_HOST} \
    --port ${WHITEPACT_PORT} \
    --workers ${WHITEPACT_WORKERS:-1} \
    --no-access-log"]
