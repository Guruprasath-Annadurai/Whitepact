# Phase 17 — Full Adversarial Hardening: Design

## Objective

Per the master directive's Phase 17 ("Full Adversarial Hardening").
`SECURITY_ASSURANCE_CASE.md` already documents 24 named threats, a
secure-design-principles argument, a common-implementation-weaknesses
matrix, and a supply-chain argument — an unusually mature existing
posture. Its own §8 "Known Limitations" states the real, remaining gap
plainly: **"No fuzz-testing or dedicated penetration test has been
performed against any surface named in this document — Bandit/
pip-audit/manual review are the current coverage, not adversarial
fuzzing."** Per directive rule 63: close what's genuinely actionable
in-repo (a real fuzz/property test against a real security boundary)
without inventing external pentest infrastructure no go-ahead exists
for.

## Audit: picking a genuine, high-value fuzz target

A dedicated third-party penetration test and general-purpose fuzzing
infrastructure are both explicitly named, correctly out-of-scope
externals (same shape as Phase 12's KMS/HSM and Phase 13's automated-
anchoring-pipeline findings — real gaps, not this phase's to close
alone). What *is* achievable: a real, narrowly-scoped
Hypothesis-based property/fuzz test against one specific,
security-critical, string-parsing boundary this codebase already has
— exactly the class of surface fuzzing exists to stress, and this
project already uses Hypothesis extensively (Phases 2, 4, 7, 16).

**Target selected**: `webhooks/manager.py::validate_webhook_url()` —
the SSRF guard. Chosen because:
- It is a single function that both `validate_webhook_url()` (webhook
  registration/delivery) and `validate_upstream_server_url()`
  (`governance/upstream.py`, upstream MCP server registration/dispatch)
  ultimately rely on — `validate_upstream_server_url()` delegates to
  it directly rather than reimplementing the check, so fuzzing this
  one function covers both real call sites.
- It parses attacker-influenced input (a URL an org admin registers)
  into a security decision (is this address safe to connect this
  server to), the canonical shape of a fuzz target.
- Its existing test coverage (`tests/test_webhooks.py::TestSSRFGuard`)
  is entirely example-based: four hand-picked non-public addresses
  (loopback, one RFC1918 address, the cloud-metadata address) and one
  hand-picked public address. The function's actual logic checks six
  `ipaddress.IPv4Address`/`IPv6Address` properties
  (`is_private`/`is_loopback`/`is_link_local`/`is_reserved`/
  `is_multicast`/`is_unspecified`) — the existing tests exercise a
  handful of specific values, not the full space those six properties
  partition.

## Design

New file `tests/test_ssrf_guard_fuzz.py`:

1. A Hypothesis property test using `st.ip_addresses(v=4)` and
   `st.ip_addresses(v=6)` (combined via `st.one_of`) to generate
   arbitrary IPv4/IPv6 addresses across the full address space —
   monkeypatch `socket.getaddrinfo` to resolve to the generated
   address, then assert `validate_webhook_url()` raises
   `UnsafeWebhookURLError` **if and only if** that address's own
   `is_private`/`is_loopback`/`is_link_local`/`is_reserved`/
   `is_multicast`/`is_unspecified` properties say it should — the
   function's own stated logic, used as the oracle, checked against
   itself across the full space Hypothesis can generate rather than
   four examples. This is a regression guard against a future edit
   subtly narrowing or widening the six-condition check (a dropped
   `or` clause, a typo'd property name) without anyone noticing,
   exactly the kind of defect a fuzz/property test catches that
   example-based tests with fixed inputs do not.
2. A smaller confirming test that `validate_upstream_server_url()`
   (`governance/upstream.py`) reaches the identical verdict as
   `validate_webhook_url()` for the same generated address — proving
   the delegation this module's own docstring claims actually holds,
   not just that the underlying function is correct in isolation.

No source file changes — `validate_webhook_url()`'s existing logic is
being tested more thoroughly, not modified; the fuzz run either
confirms it's already correct (expected, since the six conditions are
Python's own well-tested `ipaddress` stdlib properties) or surfaces a
real bug, in which case it gets fixed as this phase's own "errors
found and fixed" per the standard Phase Report template. No database
migration.
