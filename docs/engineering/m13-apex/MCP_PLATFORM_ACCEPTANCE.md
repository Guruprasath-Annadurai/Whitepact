# WhitePact-side MCP acceptance

Local broad run: **518PASS, zero skips,8warnings,697.67seconds**.
Command: `PYTHONPATH=src:. python -m pytest tests/test_mcp*.py tests/test_m13p4_mcp_lifecycle.py -q -o addopts=''`.
Runtime: Python3.11.15, mcp1.29.1, pytest9.1.1, httpx0.28.1.
Receipt `/private/tmp/apex-mcp-full-local.log`. Source was the working APEX
implementation, including the product rename changes later signed atd9bd5b30;
do not relabel this long local run a clean exact-head CI run.

This covers repository assertions for schema validation, metadata/discovery,
stdio, Streamable HTTP/SSE, OAuth/PKCE, API-key negatives, tenant/session boundaries,
lifecycle, dependency failures and live policy invalidation. Some assertions use
controlled fixtures/mocks. The existing real-process/real-TCP compatibility subset
provides actual transport evidence; none is an external provider roundtrip.
Warnings concern deprecated legacy static-key compatibility, not skipped tests.

Earlier APEX metadata repair remains: `rai_check_trust` reports its external HTTP
boundary with openWorldHint=true and describes a service's advisory report.
It is not independent execution authorization. Directory descriptive metadata is
not an authorization input. Community stdio remains explicitly ungoverned and
refused under enterprise trust-domain settings.

Classification: PROTOCOL_VERIFIED for the tested WhitePact-side contracts only.
Full consequential customer execution, independent multi-host runtime enforcement,
provider accounts and external directory discoverability remain unqualified.
See AI_PLATFORM_COMPATIBILITY.md for current provider-specific BLOCKED/NOT_TESTED
statuses; historical hosted receipt labels are not current-head qualification.
