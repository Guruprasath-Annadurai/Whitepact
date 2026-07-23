# Deploy Runbook — Hosted ResponsibleAI (PRO/ENTERPRISE)

> ## What's actually live, as of 2026-07-23
>
> The real, currently-running hosted instance is **not** the VM-based
> architecture this document was originally written for. It's a managed
> three-service stack, no VM, no Docker Compose in production:
>
> - **Compute**: [Render](https://render.com) free-tier web service
>   (`responsibleai-dashboard`), building `Dockerfile` directly from the
>   `main` branch on every push (`autoDeploy: yes`) — no VPS, no SSH-in
>   deploy step.
> - **Database**: [Supabase](https://supabase.com) managed Postgres,
>   accessed via its **transaction-mode connection pooler**
>   (`aws-1-us-west-2.pooler.supabase.com:6543`), not the direct
>   `db.<ref>.supabase.co:5432` host — the direct host resolves IPv6-only
>   and Render's network can't reach it (`OSError: Network is unreachable`,
>   discovered and fixed live during this deployment).
> - **Rate-limit backend**: [Upstash](https://upstash.com) managed Redis
>   (`rediss://` TLS endpoint), replacing the in-memory limiter.
> - **Live URL**: `https://responsibleai-dashboard.onrender.com`
>
> **Why this instead of the VM path below**: Oracle Cloud's signup wanted
> a credit card the founder didn't have; Google Cloud's billing setup was
> attempted next but its UPI payment flow hit real friction (a documented
> Google Cloud/UPI issue — a required prepayment step and account
> suspension loop) and was abandoned too. Render, Supabase, and Upstash
> all offer genuinely card-free free tiers that
> together replicate what `docker-compose.prod.yml` provides on a single
> VM — at the cost of using three separate dashboards instead of one
> `docker compose up`, and Render's free tier does not offer a permanent
> disk, which is exactly why Postgres had to move to Supabase rather than
> staying as an in-container SQLite file (the first deploy attempt lost
> its data on the next redeploy before this was fixed).
>
> **Two real code bugs surfaced getting here**, both fixed and committed:
> the `Dockerfile` was silently missing `pyotp`/`sqlalchemy`/`cryptography`
> (fixed to install via `pyproject.toml`'s own extras instead of a
> hand-maintained list), and Supabase's pooler breaks asyncpg's prepared-
> statement cache (fixed in both `db/engine.py` and `migrations/env.py`
> with `statement_cache_size=0`).
>
> The VM + Docker Compose instructions below remain valid and are kept in
> full — they're the right path if you have a card and want everything on
> one box, or if you're self-hosting on your own infrastructure rather than
> using this project's specific free-tier combination.

Exact commands for standing up `docker-compose.prod.yml` on a real server.
Written for a fresh Ubuntu 22.04 VPS — adjust package manager commands if
using a different distro. Every step here is something you run; nothing in
this file executes itself.

**Shortcut**: steps 4, 5, 8, 9, and 10 below (secret generation, `.env.prod`
creation, bringing the stack up, running migrations, and local health
verification) are automated by `./scripts/deploy.sh` — run it after step 3
(cloning the repo) and it'll do all five in one command, then tell you
exactly which steps are left (DNS, TLS, nginx, Stripe — the ones that
genuinely need a domain, a certificate authority, and a payment processor
account, none of which a script can do for you). The manual steps below are
kept in full for anyone who wants to run them by hand instead, or is
debugging what the script did.

---

## 0. Prerequisites (you do this outside the terminal)

**Note**: this whole VM-based path is the *alternative* to what's actually
live (see the callout at the top of this document). Neither Oracle Cloud
nor Google Cloud ended up being used for the real deployment — both
signup flows hit friction the founder couldn't clear (OCI wanted a card
at signup; GCP's billing setup failed via UPI). If you're following this
section, you have a working payment method and want a single-VM
architecture; pick whichever provider actually works for you rather than
assuming either of those two.

- A VPS, any provider. Considerations if you're choosing one:
  - Sizing: 2+ vCPU / 4GB+ RAM comfortably runs `docker-compose.prod.yml`'s
    four services (Postgres, Redis, dashboard, MCP HTTP) at low traffic —
    below `SLA.md`'s "Recommended (Postgres + Redis, hosted)" spec of 4+
    vCPUs per replica, so don't oversell this sizing as meeting that bar
    until upgrading to paid capacity.
  - If the provider offers a free/trial tier, check honestly whether it's
    **permanent** (like OCI's Always Free tier was) or **time-boxed**
    (like GCP's $300/90-day credit) — a time-boxed credit is a real, dated
    obligation to track (migrate or pay before it lapses), not a someday
    concern.
  - Cite the provider's own SOC 2/ISO 27001 certification status if it
    has one, the same way `compliance/VENDOR_RISK_ASSESSMENT.md` does for
    the actual live deployment's vendors — real and usable in a vendor
    security review even before this platform has its own certification
    (see `compliance/SOC2_READINESS.md`).
  - Hetzner, DigitalOcean, AWS Lightsail, OCI, GCP — all remain viable
    choices; the point of this note is not to assume any one of them
    works for you without checking their current signup requirements
    yourself first.
- A domain or subdomain you control (e.g. `api.yourcompany.com`).
- A Stripe account in live mode, if selling PRO/ENTERPRISE (skip if not billing yet).

---

## 1. Point DNS at the server

Create an A record for your subdomain pointing to the VPS's public IP:

```
api.yourcompany.com.   A   <VPS_PUBLIC_IP>
```

Wait for propagation before step 6 (TLS cert issuance fails without it):

```bash
dig +short api.yourcompany.com
# should print your VPS IP
```

---

## 2. Install Docker on the VPS

SSH in, then:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

---

## 3. Clone the repo and check out the version you want to run

```bash
git clone https://github.com/Guruprasath-Annadurai/ResponsibleAi.git
cd ResponsibleAi
git checkout main   # or a specific tag once you're cutting releases
```

---

## 4. Generate secrets

```bash
openssl rand -hex 32   # → POSTGRES_PASSWORD
openssl rand -hex 32   # → REDIS_PASSWORD
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # → RAI_API_KEYS (bootstrap key)
```

Keep these somewhere durable (a password manager) — losing `POSTGRES_PASSWORD`
after data exists means you lose access to the database, not just a login.

---

## 5. Configure `.env.prod`

```bash
cp .env.prod.example .env.prod
```

Edit `.env.prod` and fill in:
- `POSTGRES_PASSWORD`, `REDIS_PASSWORD` — from step 4
- `RAI_API_KEYS` — the bootstrap key from step 4 (used once to create the first org, then rotate to org-scoped DB keys)
- `RAI_ALLOWED_ORIGINS` — `https://api.yourcompany.com` (or your dashboard's actual origin)
- Stripe block — only if billing live now; safe to leave commented and add later
- OIDC block — only if SSO is set up now; safe to leave commented and add later

```bash
chmod 600 .env.prod   # don't leave secrets world-readable
```

---

## 6. TLS — issue a certificate

```bash
sudo apt update && sudo apt install -y certbot
sudo certbot certonly --standalone -d api.yourcompany.com
# cert lands in /etc/letsencrypt/live/api.yourcompany.com/
```

`--standalone` needs port 80 free — stop anything bound to it first, or use
`--webroot` if nginx is already running.

---

## 7. nginx reverse proxy

```bash
sudo apt install -y nginx
```

`/etc/nginx/sites-available/responsibleai`:

```nginx
upstream rai_dashboard { server 127.0.0.1:8765; }
upstream rai_mcp       { server 127.0.0.1:8766; }

server {
    listen 443 ssl;
    server_name api.yourcompany.com;

    ssl_certificate     /etc/letsencrypt/live/api.yourcompany.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourcompany.com/privkey.pem;

    client_max_body_size 10m;

    location / {
        proxy_pass http://rai_dashboard;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Hosted MCP — SSE needs long-lived connections, buffering off.
    location /mcp/ {
        proxy_pass http://rai_mcp/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;
        proxy_read_timeout 3600s;
    }
}

server {
    listen 80;
    server_name api.yourcompany.com;
    return 301 https://$host$request_uri;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/responsibleai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Renewal is automatic via certbot's systemd timer — verify it's active:

```bash
sudo systemctl status certbot.timer
```

---

## 8. Bring up the stack

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
docker compose -f docker-compose.prod.yml ps
```

All four containers (`rai-postgres`, `rai-redis`, `rai-dashboard`, `rai-mcp-http`)
should show `healthy` within ~30s. If not:

```bash
docker compose -f docker-compose.prod.yml logs dashboard --tail 100
```

---

## 9. Run database migrations

The compose stack starts the app but doesn't run Alembic automatically —
do it explicitly the first time and after every schema change. The
container already has `RAI_DATABASE_URL` set from `docker-compose.prod.yml`,
so no need to reconstruct it by hand:

```bash
docker compose -f docker-compose.prod.yml exec dashboard alembic upgrade head
```

Verify it applied cleanly:

```bash
docker compose -f docker-compose.prod.yml exec dashboard alembic current
# should print: 0010 (head)
```

---

## 10. Verify it's actually live

```bash
curl -s https://api.yourcompany.com/api/health | python3 -m json.tool
curl -s https://api.yourcompany.com/api/support/status | python3 -m json.tool
curl -s https://api.yourcompany.com/mcp/health | python3 -m json.tool
```

`/api/health` returns HTTP 503 (not 200) when its database check fails —
this is what a load balancer or orchestrator health probe should key off,
not the JSON body's `status` field, since most LB health checks only look
at the status code.

Port 8766 (MCP HTTP) is only bound to `127.0.0.1` on the VPS per the compose
file — it's not reachable directly from outside, only through nginx's
`/mcp/` path above. That's intentional, not a bug to work around.

Open `https://api.yourcompany.com/status` in a browser — the status page
from Phase 2 should show green and the correct version.

---

## 11. Create your first real org (retire the bootstrap key)

```bash
curl -s -X POST https://api.yourcompany.com/api/orgs \
  -H "Authorization: Bearer <RAI_API_KEYS bootstrap key from step 4>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Your First Customer", "slug": "first-customer"}'
# → returns {"id": "...", ...}

curl -s -X POST https://api.yourcompany.com/api/orgs/<org_id>/keys \
  -H "Authorization: Bearer <bootstrap key>" \
  -H "Content-Type: application/json" \
  -d '{"name": "primary", "role": "OWNER"}'
# → returns the raw key ONCE — save it, it's not recoverable
```

After every real org has its own key, remove `RAI_API_KEYS` from `.env.prod`
and restart — the flat bootstrap key is a legacy super-admin path, not
something to leave live indefinitely.

---

## 12. Wire Stripe (if selling now)

1. In the Stripe dashboard, create two recurring Prices (PRO, ENTERPRISE) matching the amounts in `mcp/licensing.py`'s `plan_catalog()`.
2. Add a webhook endpoint pointing at `https://api.yourcompany.com/api/v1/billing/webhook`, subscribed to: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`.
3. Copy the webhook signing secret and the two Price IDs into `.env.prod`'s Stripe block.
4. Restart: `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d dashboard`
5. Test with Stripe's test-mode keys first — flip to live keys only after a successful test checkout end-to-end.

---

## 13. Public status page (statuspage.io or equivalent) — manual, external

This step needs your account, not a command:

1. Sign up at statuspage.io (or Better Uptime / UptimeRobot — any works).
2. Add a monitor pointing at `https://api.yourcompany.com/api/support/status`, checking the `status` field for `"operational"`.
3. Publish the page, get its URL.
4. Come back and update `SLA.md`'s "Uptime status page" section with the real link — it currently says none exists; that sentence should be replaced once one does.

---

## 13b. Multi-region / high availability — what's actually true here

Stated plainly, not aspirationally:

- **This runbook stands up one instance in one region.** There is no
  multi-region active-active topology in this repo, and no code here can
  substitute for one — that's infrastructure the deployer builds (a global
  load balancer routing to independent regional stacks, each with its own
  Postgres and Redis, plus a data-replication strategy across regions).
  Nothing above provisions that.
- **What this version *does* give you toward within-region HA:**
  - `DatabaseEngine.init()` retries transient Postgres connection failures
    with backoff (see `db/engine.py`) — it tolerates a managed database's
    failover window, it doesn't perform the failover itself.
  - Webhook delivery retries and webhook *registrations* are both DB-backed
    (`webhook_deliveries`, `webhook_configs` — migration 0010), so either
    survives a container restart or a second replica picking up where the
    first left off.
  - The webhook retry worker claims pending retries atomically
    (`WebhookDeliveryRepository.pending_retries()`), so running more than
    one replica doesn't double-fire the same webhook delivery.
  - The dashboard itself is stateless (no server-side session — the
    browser holds its own bearer token), so the app tier can run as
    multiple replicas behind a load balancer *once* its dependencies are
    shared, not per-replica (see next point).
- **Set `RAI_MULTI_REPLICA=true` if you run more than one instance.** This
  doesn't change behavior by itself — it's a self-declaration that makes
  startup check whether your configuration can actually support that
  honestly, and log a `multi_replica_misconfigured` warning if not:
  - SQLite (the default) is a single file. Two replicas both writing to it
    isn't "slower," it's a correctness problem. Set `RAI_DATABASE_URL` to a
    shared Postgres instance before running more than one replica.
  - In-memory rate limiting is per-process. Two replicas each enforce their
    *own* counter, so a "100/minute" limit silently becomes "up to 100 ×
    replica-count per minute" in aggregate — no error, just a limit that
    doesn't do what its number says. Set `RAI_REDIS_URL` before running
    more than one replica.
- **Practical near-term HA path or once actual multi-instance traffic
  justifies it:** one region, N app-tier replicas behind a load balancer,
  a managed Postgres with automatic failover (e.g. RDS Multi-AZ, Cloud SQL
  HA, or a self-managed Patroni cluster), and a managed or clustered Redis.
  That's a meaningfully different (and higher-cost) deployment than the
  single-VPS `docker-compose.prod.yml` this runbook automates — treat it as
  the next infrastructure milestone, not something achievable by flipping
  a flag.

---

## 14. Post-deploy checklist

- [ ] `docker compose ps` shows all 4 services healthy
- [ ] `alembic current` shows `0010 (head)`
- [ ] `/api/health`, `/api/support/status`, `/status` all reachable over HTTPS
- [ ] TLS cert valid (`curl -vI https://api.yourcompany.com 2>&1 | grep -i expire`)
- [ ] Bootstrap `RAI_API_KEYS` removed after first org+key created
- [ ] `.env.prod` permissions are `600`, not committed to git (confirm: `git status` shows it untracked)
- [ ] Stripe webhook delivering successfully (check Stripe dashboard's webhook logs after a test event)
- [ ] Public status page live and linked from `SLA.md`
- [ ] `RAI_ALLOWED_ORIGINS` matches your actual dashboard origin (not `*`)
- [ ] Postgres/Redis ports confirmed NOT reachable from outside the VPS (`docker compose -f docker-compose.prod.yml ps` — no public port mapping on those two)

---

## Updating to a new version later

```bash
git pull origin main
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml exec dashboard alembic upgrade head   # if a new migration shipped
docker compose -f docker-compose.prod.yml up -d
```
