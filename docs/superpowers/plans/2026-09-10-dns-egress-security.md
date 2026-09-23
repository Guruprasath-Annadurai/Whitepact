# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

# WhitePact DNS Rebinding & Outbound Egress Security Implementation Plan

**Date:** 2026-09-10  
**Status:** Approved for Implementation  
**Baseline SHA:** `39fda2c524aa0c5e8d58cb8713bf5c1275c7bc09`  
**Target Branch:** `audit/dns-egress-security-closure`  

---

## Execution Phases

### Phase 1: Adversarial Reproduction (RED Tests)
- Create `tests/test_dns_egress_security.py`.
- Implement synthetic local listeners and controlled resolver abstractions.
- Add RED test cases:
  1. `test_dns_rebinding_reaches_forbidden_listener_unpatched`: Proves that a hostname validated as public connects to a loopback listener when DNS changes before socket connect.
  2. `test_mixed_safe_and_unsafe_dns_answers`: Proves ambiguity when resolver returns both public and private addresses.
  3. `test_static_forbidden_destinations`: Covers RFC1918, loopback, link-local, metadata (`169.254.169.254`), IPv6 ULA, IPv4-mapped IPv6, CGNAT, and obfuscated representations.
  4. `test_proxy_environment_variable_bypass`: Verifies that `HTTP_PROXY` / `ALL_PROXY` cannot divert outbound traffic.
  5. `test_unsafe_redirect_chain`: Verifies that a redirect from a public server to loopback or a rebinding target is blocked.
  6. `test_retry_rebind`: Verifies that transient failure retries cannot re-resolve to a forbidden internal address.

### Phase 2: Safe Outbound Network Boundary Implementation
- Create package `src/responsibleai/net/`:
  - `src/responsibleai/net/__init__.py`
  - `src/responsibleai/net/egress.py`:
    - `EgressSecurityError`, `ForbiddenDestinationError`, `DNSResolutionError`, `PeerMismatchError`
    - `DestinationPolicy` (PUBLIC_ONLY, TRUSTED_PRIVATE)
    - `is_address_allowed(ip_str_or_obj, policy)`
    - `validate_outbound_url(url, policy)`
    - `AsyncDNSResolver` and `SystemDNSResolver`
    - `SafeNetworkBackend(httpcore.AsyncNetworkBackend)`
    - `SafeAsyncHTTPTransport(httpx.AsyncHTTPTransport)`
    - `create_safe_async_client(...)`

### Phase 3: Integration into Outbound Call Sites
- Integrate into `responsibleai.webhooks.manager`:
  - Update `validate_webhook_url` to use `validate_outbound_url`.
  - Update `_deliver` to use `create_safe_async_client()`.
- Integrate into `responsibleai.governance.upstream_executor`:
  - Update `_default_http_client_factory` to return `create_safe_async_client(timeout=UPSTREAM_CALL_TIMEOUT_SECONDS)`.
  - Update `validate_upstream_server_url`.
- Integrate into `responsibleai.governance.upstream_discovery`:
  - Ensure all tool listing calls use the safe client factory.

### Phase 4: Verification & Quality Gates
- Run new adversarial suite `tests/test_dns_egress_security.py` -> All GREEN.
- Run webhook test suite `tests/test_tenant_isolation_webhooks.py`.
- Run upstream MCP test suite `tests/test_upstream_gateway.py`.
- Run quality gates:
  - `ruff check src tests`
  - `mypy src/responsibleai tests/test_dns_egress_security.py`
  - `python scripts/manage_license_headers.py --check`
  - `git diff --check`
  - `gitleaks dir --verbose`
  - `gitleaks git --verbose`
- Run full repository pytest suite.

### Phase 5: Documentation & Closure Report
- Create `docs/security/DNS_EGRESS_SECURITY_CLOSURE.md`.
- Generate the final formal closure report.
