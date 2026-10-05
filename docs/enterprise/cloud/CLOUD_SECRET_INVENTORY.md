# Cloud secret inventory (types only)

Also referenced as production/staging secret inventory. **No values in Git.**

| Secret type | Consumer | Rotation | Storage (staging target) |
|-------------|----------|----------|---------------------------|
| `HCLOUD_TOKEN` | Terraform / deploy | On compromise | CI secret / operator env |
| `CLOUDFLARE_API_TOKEN` | DNS, R2, WAF | Quarterly | CI secret (zone-scoped) |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | Backup upload | On role change | Authority host env / SSM equivalent |
| `POSTGRES_PASSWORD` | App + migrations | On restore drill | `.env.prod` on authority (not in repo) |
| `REDIS_PASSWORD` | App | With DB rotation | SaaS host env |
| `WHITEPACT_SECRET_KEY` / session signing | Dashboard | Quarterly | SaaS env |
| `RAI_ENCRYPTION_KEY` / field encryption | Governance store | Controlled migration | Authority env |
| CSRF / cookie secrets | Web | With app secret | SaaS env |
| OIDC / SSO client secrets | Enterprise SSO | Per IdP | SaaS env (test IdP only in staging) |
| SCIM bearer tokens | Provisioning | Per tenant test | SaaS env |
| Paddle API keys | Billing | N/A staging | **Sandbox only** — not production |
| SMTP / email API | Auth emails | Per provider | SaaS env |
| OTEL exporter headers | Telemetry | Quarterly | SaaS env |
| MCP upstream credentials | Execution tier | Per integration | Execution env |
| Terraform state encryption key | IaC | Rare | Remote backend config |
| SSH host keys | Operators | On rebuild | Host-local |
| Cloudflare Origin Pull cert/key | Origin mTLS | Per CF docs | Origin/LB |

## Generation

Use `openssl rand -base64 32` or platform KMS. Never reuse CI/dev secrets.

## Rotation procedure (outline)

1. Generate new secret in secure store.
2. Dual-write or maintenance window.
3. Revoke old credential.
4. Audit log + evidence entry in `CLOUD_DEPLOYMENT_EVIDENCE.md`.
