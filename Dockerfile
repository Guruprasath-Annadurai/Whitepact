# The human-readable tag documents the intended update line; the digest makes
# the actual build input immutable for supply-chain reproducibility / OpenSSF
# Pinned-Dependencies. Update both together after reviewing a new upstream
# Python image.
FROM python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17 AS builder

WORKDIR /build
COPY requirements-build.lock ./
RUN python -m pip install --require-hashes -r requirements-build.lock
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN python -m build --no-isolation --wheel --outdir /dist


FROM python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17 AS runtime

LABEL org.opencontainers.image.title="ResponsibleAI Governance Platform"
LABEL org.opencontainers.image.description="Enterprise AI Governance — Trust Scoring, Compliance, Cost Intelligence"
LABEL org.opencontainers.image.version="1.2.0"
LABEL org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RAI_HOST=0.0.0.0 \
    RAI_PORT=8765 \
    RAI_LOG_JSON=true \
    RAI_DB_PATH=/data/responsibleai.db

RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/sh --create-home appuser

RUN mkdir -p /data && chown appuser:appgroup /data

WORKDIR /app
COPY --from=builder /dist/*.whl /tmp/
COPY requirements-container.lock ./
# The fully resolved, hash-locked runtime closure is installed first. Installer
# then adds the locally built wheel without resolving or downloading anything.
RUN python -m pip install --require-hashes -r requirements-container.lock && \
    python -m installer /tmp/*.whl

COPY src/responsibleai/dashboard/static/ /app/static/
COPY alembic.ini ./
COPY migrations/ ./migrations/

USER appuser

EXPOSE 8765 8766

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import json,sys,urllib.request; d=json.load(urllib.request.urlopen('http://localhost:8765/api/health', timeout=4)); sys.exit(0 if d['status'] in ('healthy','degraded') else 1)"

CMD ["sh", "-c", "uvicorn responsibleai.dashboard.app:app \
    --host ${RAI_HOST} \
    --port ${RAI_PORT} \
    --workers ${RAI_WORKERS:-1} \
    --no-access-log"]
