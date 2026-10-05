# Origin protection (addresses ORIGIN-LIVE-BYPASS)

**M6 defect:** `ORIGIN-LIVE-BYPASS` — requires **live** evidence after staging deploy.

## Principles

1. Direct connection to origin IP must **not** bypass Cloudflare WAF/rate limits.
2. TLS **Full (strict)** end-to-end — no Cloudflare Flexible SSL.
3. Header-based “security” without network enforcement is **insufficient**.

## Mechanisms (verify against current provider docs before apply)

| Control | Role | Reference |
|---------|------|-----------|
| Orange-cloud DNS only | Hides origin from casual users | Cloudflare proxy |
| Hetzner firewall on LB / SaaS | Ingress **only** from [Cloudflare IP ranges](https://www.cloudflare.com/ips/) | Network allowlist |
| Authenticated Origin Pulls | mTLS from Cloudflare to origin | [Authenticated Origin Pull](https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/) |
| `saas_public_ipv4 = false` | No app on public NIC | `whitepact-hetzner-foundation` |
| Cloudflare Tunnel (optional) | No inbound origin port | Use for admin; evaluate for SaaS if needed |

## Implementation checklist (post–Gate 1)

- [ ] LB public IP; SaaS nodes private-only
- [ ] Firewall rules: drop non-Cloudflare sources on 80/443
- [ ] Enable Authenticated Origin Pull on zone + origin cert
- [ ] Negative test: `curl https://<origin-ip>/` from arbitrary VPS → **connection refused or TLS fail**
- [ ] Positive test: via staging hostname → 200 on `/livez`
- [ ] Record evidence in `CLOUD_DEPLOYMENT_EVIDENCE.md`

## Product configuration

- Do **not** set `RAI_MCP_HTTP_TRUST_FORWARDED=true` on interfaces reachable without CF/LB enforcement.
- Dashboard reverse proxy must pass client IP only from trusted hop.
