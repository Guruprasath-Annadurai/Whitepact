# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

# WhitePact DNS Rebinding & Outbound Egress Security Design

**Date:** 2026-09-10  
**Status:** Approved for Implementation  
**Baseline SHA:** `39fda2c524aa0c5e8d58cb8713bf5c1275c7bc09`  
**Target Branch:** `audit/dns-egress-security-closure`  
**Author:** Principal Application Security & Network Boundary Engineer  

---

## 1. Problem Statement & Threat Model

### 1.1 The Vulnerability
WhitePact currently executes outbound HTTP requests for two primary user-controlled features:
1. **Outgoing Webhooks** (`responsibleai.webhooks.manager.WebhookManager`)
2. **Upstream MCP Servers** (`responsibleai.governance.upstream_executor.UpstreamMCPExecutor`)

In the baseline codebase, URL validation is performed via `validate_webhook_url(url)` (and its alias `validate_upstream_server_url(url)`). This function resolves the URL host via `socket.getaddrinfo(host, None)` and inspects `ip.is_private`, `is_loopback`, etc. However, after `validate_webhook_url` completes:
- An independent `httpx.AsyncClient()` instance is constructed.
- The HTTP client executes `client.post(url)` or `streamable_http_client(url)`.
- The underlying transport (`httpcore.AsyncConnectionPool` / `anyio.connect_tcp`) performs its **own independent DNS resolution**.

This creates a severe **Time-Of-Check to Time-Of-Use (TOCTOU) DNS Rebinding** vulnerability:
1. An attacker configures a webhook or upstream MCP server pointing to `attacker.example`.
2. On initial validation, `attacker.example` responds with a public IP (`203.0.113.10`, TTL=0). Validation passes.
3. Milliseconds later when `httpx` connects, `attacker.example` responds with `127.0.0.1` or `169.254.169.254`.
4. The server establishes an unmonitored TCP connection to an internal loopback service, database, or cloud metadata service.
5. In addition:
   - **Mixed DNS responses:** If `attacker.example` returns `[203.0.113.10, 127.0.0.1]`, the client may connect to the loopback address.
   - **Redirect Rebinding:** A safe endpoint returns a 302 redirect to a rebinding domain or private IP.
   - **Proxy Environment Leaks:** Default `httpx.AsyncClient` trusts `HTTP_PROXY` / `ALL_PROXY`, routing requests through unauthenticated local proxies.
   - **Retry Rebinding:** On transient connection errors, subsequent retry attempts may resolve to forbidden private addresses.

---

## 2. Complete Inventory of Outbound Call Sites

| Path ID | File / Function | User Controllable | Host Validated | IP Validated | Pre-Resolved | Connect IP Bound | Redirects | Proxies | Retries | Environment |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **OUT-01** | `responsibleai.webhooks.manager::WebhookManager._deliver` | **YES** | YES | YES | YES | **NO** | `follow=False` | `trust_env=True` (defect) | YES | Official Production |
| **OUT-02** | `responsibleai.governance.upstream_executor::_call_upstream_tool` | **YES** | YES | YES | YES | **NO** | `follow=False` | `trust_env=True` (defect) | YES | Official Production |
| **OUT-03** | `responsibleai.governance.upstream_discovery::_list_tools_for_server` | **YES** | YES | YES | YES | **NO** | `follow=False` | `trust_env=True` (defect) | NO | Official Production |
| **OUT-04** | `responsibleai.dashboard.transactional_email::AuthenticatedWebhookEmailProvider.deliver` | **NO** (Operator `.env`) | NO | NO | NO | **NO** | `follow=False` | `trust_env=True` | YES | Official Production |
| **OUT-05** | `responsibleai.auth.oidc::AsyncJWKSClient._refresh` | **NO** (Operator `.env`) | NO | NO | NO | **NO** | `follow=False` | `trust_env=True` | YES | Official Production |
| **OUT-06** | `responsibleai.auth.oidc::OIDCProvider.discover` | **NO** (Operator `.env`) | NO | NO | NO | **NO** | `follow=False` | `trust_env=True` | NO | Official Production |
| **OUT-07** | `biasbuster.providers.huggingface_provider::OllamaProvider.complete` | **PARTIAL** (Local host) | NO | NO | NO | **NO** | default | default | NO | Community / Local |
| **OUT-08** | `responsibleai.integrations.client::ResponsibleAIClient.check_async` | N/A (Client SDK) | N/A | N/A | N/A | N/A | default | default | NO | Client SDK |

**Summary:** Exactly two core user-controllable official production outbound paths exist:
1. **Webhooks** (`OUT-01`)
2. **Upstream MCP Servers** (`OUT-02`, `OUT-03`)

Both currently suffer from DNS rebinding and unbound connect-time destinations.

---

## 3. Evaluation of Implementation Approaches

### Approach A: Pre-validation only (Status Quo)
- **Concept:** Call `validate_webhook_url` before `httpx.post`.
- **Flaw:** High risk TOCTOU. Does not bind socket connect destination to the validated IP. Vulnerable to DNS rebinding, TTL=0 racing, and mixed A/AAAA records.
- **Verdict:** REJECTED (Known broken).

### Approach B: Application-layer URL rewriting to IP
- **Concept:** Resolve hostname, validate IP, rewrite URL to `http://<ip>/...`, and pass `headers={"Host": hostname}`.
- **Flaw:** Completely breaks TLS/HTTPS. TLS SNI requires the hostname; certificate verification fails when connecting to an IP literal unless certificate hostname verification is disabled or monkey-patched. Disabling verification violates hard invariant.
- **Verdict:** REJECTED (Violates TLS security invariants).

### Approach C: Custom `AsyncNetworkBackend` + Controlled `AsyncHTTPTransport` (Selected)
- **Concept:** 
  1. Provide a standard, reusable network boundary module `responsibleai.net.egress`.
  2. Implement `SafeNetworkBackend(httpcore.AsyncNetworkBackend)` that intercepts `connect_tcp`.
  3. Inside `connect_tcp`:
     - Resolve target hostname to all candidate IP addresses (A + AAAA).
     - Fail closed if any candidate belongs to a forbidden class (loopback, private, link-local, multicast, metadata, CGNAT, etc.).
     - Select a validated safe IP candidate and connect via the underlying OS socket primitive.
     - Verify connected peer address via `stream.get_extra_info("server_addr")`.
  4. Pass the connected stream to `httpcore.AsyncHTTPConnection`, which performs `stream.start_tls(server_hostname=origin.host.decode("ascii"))`.
     - TLS SNI is preserved.
     - TLS certificate verification is preserved with full root validation (`verify=True`).
     - HTTP `Host` header is preserved.
     - `trust_env=False` is enforced, preventing proxy bypass.
     - Unix domain sockets are explicitly forbidden.
- **Verdict:** **ACCEPTED** — Clean, standard networking primitives, zero monkey-patching, mathematically eliminates TOCTOU by binding DNS validation directly to socket connect.

---

## 4. Architectural Component Specification

```
User Request (Webhook / Upstream MCP)
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  responsibleai.net.egress.DestinationGuard             │
│  - Validate URL syntax & scheme (http/https only)     │
│  - Normalize host (IDNA, strip trailing dots)          │
│  - Reject malformed / obfuscated IP literals           │
└────────────────────────┬───────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│  responsibleai.net.egress.SafeNetworkBackend           │
│  - Intercepts httpcore `connect_tcp`                   │
│  - Resolves all A and AAAA records                     │
│  - Validates all candidate addresses against policy   │
│  - Connects strictly to validated IP candidate        │
│  - Post-connect peer verification                      │
│  - Forbids UDS & rejects proxy environment             │
└────────────────────────┬───────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│  httpcore.AsyncHTTPConnection                          │
│  - TLS handshake with server_hostname=original_host    │
│  - Standard cert verification preserved (verify=True) │
│  - HTTP Host header preserved                          │
└────────────────────────┬───────────────────────────────┘
                         │
                         ▼
             Remote Public Endpoint
```

### 4.1 Forbidden Address Classes
The address validator will reject:
- `127.0.0.0/8` and `::1` (Loopback)
- `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` (RFC1918 Private)
- `169.254.0.0/16` and `fe80::/10` (Link-Local)
- `fc00::/7` (Unique Local Address - ULA)
- `100.64.0.0/10` (Carrier-Grade NAT)
- `0.0.0.0/8` and `::` (Unspecified)
- `224.0.0.0/4` and `ff00::/8` (Multicast)
- `255.255.255.255/32` (Broadcast)
- `169.254.169.254` and `[fd00:ec2::254]` (Cloud Metadata)
- IPv4-mapped IPv6 equivalents of all the above (e.g. `::ffff:127.0.0.1`)
- Obfuscated decimal/hex/octal representations (e.g. `2130706433`, leading-zero octals).

---

## 5. Security & Invariant Checklist

- [x] Deterministic validation: All resolved addresses must be safe; mixed safe/unsafe fails closed.
- [x] Connect-time binding: Socket connects strictly to a pre-validated IP.
- [x] Host / SNI preservation: TLS certificate validation is untouched (`verify=True`).
- [x] Proxy isolation: `trust_env=False` prevents environmental proxy redirection.
- [x] Redirect safety: Every redirect destination passes through the same `SafeNetworkBackend`.
- [x] No custom DNS server: Uses Python's native `socket.getaddrinfo` with pluggable resolver abstraction for testing.
- [x] Minimal coupling: Reusable `responsibleai.net.egress` package used by webhooks and upstream MCP.
