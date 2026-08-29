"""Tests for Enterprise Neural Phase 17 (Full Adversarial Hardening).

Per `docs/enterprise-neural/17_PHASE17_DESIGN.md`:
`SECURITY_ASSURANCE_CASE.md` §8 states plainly that no fuzz-testing has
been performed against any surface in this codebase. This file closes
that gap for one real, security-critical target:
`webhooks/manager.py::validate_webhook_url()`, the SSRF guard both
webhook delivery and upstream MCP server registration/dispatch
(`governance/upstream.py::validate_upstream_server_url()`) rely on.

The function's own logic checks six `ipaddress` properties
(`is_private`/`is_loopback`/`is_link_local`/`is_reserved`/
`is_multicast`/`is_unspecified`). Existing coverage
(`tests/test_webhooks.py::TestSSRFGuard`) exercises five hand-picked
addresses. This file uses Hypothesis's `ip_addresses` strategy to
generate arbitrary IPv4/IPv6 addresses across the full space those six
properties partition, using the function's own stated logic as the
oracle -- a regression guard against a future edit subtly narrowing or
widening the check without anyone noticing, which fixed example inputs
cannot catch.
"""

from __future__ import annotations

import ipaddress

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from responsibleai.governance.upstream import (
    UnsafeUpstreamServerURLError,
    validate_upstream_server_url,
)
from responsibleai.webhooks.manager import UnsafeWebhookURLError, validate_webhook_url


def _should_be_rejected(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """The exact six-condition oracle validate_webhook_url() itself
    states it checks -- kept as a standalone predicate so the test
    doesn't import the function's internals, only re-derive the same
    documented properties."""
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


_ip_strategy = st.one_of(st.ip_addresses(v=4), st.ip_addresses(v=6))


class TestValidateWebhookURLAgainstTheFullAddressSpace:
    @given(addr=_ip_strategy)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_verdict_matches_the_documented_six_condition_oracle(
        self, monkeypatch: pytest.MonkeyPatch, addr: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> None:
        monkeypatch.setattr(
            "responsibleai.webhooks.manager.socket.getaddrinfo",
            lambda host, *a, **k: [(2, 1, 6, "", (str(addr), 0))],
        )
        expect_rejected = _should_be_rejected(addr)

        if expect_rejected:
            with pytest.raises(UnsafeWebhookURLError, match="non-public"):
                validate_webhook_url("https://probe.example.com/hook")
        else:
            validate_webhook_url("https://probe.example.com/hook")  # must not raise


class TestValidateUpstreamServerURLDelegatesIdentically:
    """governance/upstream.py's own docstring claims it delegates to
    validate_webhook_url() rather than reimplementing the check --
    proven here across the same generated space, not assumed from
    reading the one-line try/except that wraps the call."""

    @given(addr=_ip_strategy)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_same_verdict_as_validate_webhook_url(
        self, monkeypatch: pytest.MonkeyPatch, addr: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> None:
        monkeypatch.setattr(
            "responsibleai.webhooks.manager.socket.getaddrinfo",
            lambda host, *a, **k: [(2, 1, 6, "", (str(addr), 0))],
        )
        expect_rejected = _should_be_rejected(addr)

        if expect_rejected:
            with pytest.raises(UnsafeUpstreamServerURLError):
                validate_upstream_server_url("https://probe.example.com/mcp")
        else:
            validate_upstream_server_url("https://probe.example.com/mcp")  # must not raise
