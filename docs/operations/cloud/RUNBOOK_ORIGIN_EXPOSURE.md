# Runbook — origin exposure / ORIGIN-LIVE-BYPASS

**Trigger:** Origin IP reachable without Cloudflare path; WAF bypass suspected.

**Contain:** Hetzner firewall — restrict 80/443 to Cloudflare IPs; enable Authenticated Origin Pull.

**Verify:** Negative curl from external VPS; positive via proxied hostname.

**Recover:** Rotate origin if leaked; update DNS only via approved change window.

**Evidence:** Firewall rule IDs, test outputs in `CLOUD_DEPLOYMENT_EVIDENCE.md`.

**Escalate:** Security lead immediately.
