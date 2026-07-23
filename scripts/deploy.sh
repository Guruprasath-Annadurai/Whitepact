#!/usr/bin/env bash
# One-command bring-up for the self-hosted production stack
# (docker-compose.prod.yml — Postgres + Redis, multi-replica-capable).
#
# This automates the *automatable* part of DEPLOY_RUNBOOK.md — secret
# generation, env file creation, bringing the stack up, waiting for health,
# and running migrations (steps 4/5/8/9/10 there). It deliberately does
# NOT touch DNS, TLS certificates, nginx, or Stripe — those need a domain
# you control, a certificate authority interaction, and a real payment
# processor account, none of which a script can or should do on your
# behalf. Do those manually per DEPLOY_RUNBOOK.md steps 1, 6, 7, and 12.
#
# Usage:
#   ./scripts/deploy.sh                 # first-time bring-up or redeploy
#   ./scripts/deploy.sh --migrate-only  # just (re)run migrations against an already-running stack
#
# Idempotent: safe to re-run. Won't overwrite an existing .env.prod.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

COMPOSE="docker compose -f docker-compose.prod.yml"
ENV_FILE=".env.prod"

log() { echo "[$(date -u +%FT%TZ)] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

if [[ "${1:-}" == "--migrate-only" ]]; then
  [[ -f "$ENV_FILE" ]] || die "$ENV_FILE not found — run this script without --migrate-only first."
  log "Running migrations only..."
  $COMPOSE --env-file "$ENV_FILE" exec -T dashboard alembic upgrade head
  $COMPOSE --env-file "$ENV_FILE" exec -T dashboard alembic current
  exit 0
fi

# ── 1. Preflight ──────────────────────────────────────────────────────────────

command -v docker &> /dev/null || die "Docker is required. Install: https://docs.docker.com/get-docker/"
docker compose version &> /dev/null || die "Docker Compose v2 is required (docker compose, not docker-compose)."

# ── 2. Generate .env.prod if it doesn't exist yet ────────────────────────────

if [[ -f "$ENV_FILE" ]]; then
  log "$ENV_FILE already exists — leaving it untouched. Delete it first if you want fresh generated secrets."
else
  [[ -f ".env.prod.example" ]] || die ".env.prod.example not found — can't generate $ENV_FILE."
  log "Generating $ENV_FILE with fresh random secrets..."

  postgres_password="$(openssl rand -hex 32)"
  redis_password="$(openssl rand -hex 32)"
  bootstrap_key="rai_$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

  sed \
    -e "s#^POSTGRES_PASSWORD=.*#POSTGRES_PASSWORD=${postgres_password}#" \
    -e "s#^REDIS_PASSWORD=.*#REDIS_PASSWORD=${redis_password}#" \
    -e "s#^RAI_API_KEYS=.*#RAI_API_KEYS=${bootstrap_key}#" \
    .env.prod.example > "$ENV_FILE"

  chmod 600 "$ENV_FILE"

  log "Generated $ENV_FILE (mode 600, not tracked by git)."
  log "Bootstrap API key (save this now — shown once, needed for DEPLOY_RUNBOOK.md step 11):"
  echo "    ${bootstrap_key}"
  log "RAI_ALLOWED_ORIGINS still says https://your-dashboard.example.com — edit $ENV_FILE"
  log "before exposing this to real traffic. Same for the commented-out OIDC/Stripe/OTEL blocks."
fi

# ── 3. Bring the stack up ─────────────────────────────────────────────────────

log "Building and starting the stack..."
$COMPOSE --env-file "$ENV_FILE" up -d --build

# ── 4. Wait for all services to report healthy ───────────────────────────────

log "Waiting for services to become healthy (up to 2 minutes)..."
deadline=$(($(date +%s) + 120))
while true; do
  statuses="$($COMPOSE --env-file "$ENV_FILE" ps --format '{{.Name}} {{.Health}}' 2>/dev/null || true)"
  unhealthy="$(echo "$statuses" | grep -v -E '(healthy|running)$' || true)"
  if [[ -z "$unhealthy" ]]; then
    log "All services healthy."
    break
  fi
  if [[ "$(date +%s)" -ge "$deadline" ]]; then
    echo "$statuses"
    die "Timed out waiting for services to become healthy. Check logs: $COMPOSE logs --tail 100"
  fi
  sleep 3
done

# ── 5. Run database migrations ────────────────────────────────────────────────

log "Running Alembic migrations..."
$COMPOSE --env-file "$ENV_FILE" exec -T dashboard alembic upgrade head
current="$($COMPOSE --env-file "$ENV_FILE" exec -T dashboard alembic current)"
log "Migration head: ${current}"

# ── 6. Local verification ─────────────────────────────────────────────────────

log "Verifying health endpoints (local, pre-TLS)..."
curl -fsS http://127.0.0.1:8765/api/health | python3 -m json.tool
curl -fsS http://127.0.0.1:8766/health | python3 -m json.tool

log "Stack is up and migrated. Remaining steps are the ones this script"
log "deliberately doesn't automate — see DEPLOY_RUNBOOK.md:"
log "  - Step 1:  point DNS at this host"
log "  - Step 6:  issue a TLS certificate (certbot)"
log "  - Step 7:  configure the nginx reverse proxy"
log "  - Step 11: create your first real org and retire the bootstrap key"
log "  - Step 12: wire Stripe, only once you're ready to sell live"
