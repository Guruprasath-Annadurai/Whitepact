"""Tests for Enterprise Neural Phase 12 (Platform + Network + Service
Isolation): `mcp/server.py`'s `platform_isolation_problems()`.

Per `docs/enterprise-neural/12_PHASE12_DESIGN.md`: `THREAT_MODEL.md`
already documents DNS rebinding protection defaulting to disabled for
the hosted MCP transport, but nothing gave a deployer startup-time
visibility into that state — unlike `dashboard.config.multi_replica_problems()`,
an existing precedent for exactly this shape of check. This file tests
the pure function only, matching `tests/test_config.py`'s own
`TestMultiReplicaProblems` convention (which likewise never boots a
real app to exercise the startup log line it feeds).
"""

from __future__ import annotations

from responsibleai.mcp.server import platform_isolation_problems


class TestPlatformIsolationProblems:
    def test_disabled_transport_security_is_flagged(self) -> None:
        problems = platform_isolation_problems(transport_security_enabled=False)
        assert len(problems) == 1
        assert "DNS rebinding" in problems[0]

    def test_enabled_transport_security_is_clean(self) -> None:
        problems = platform_isolation_problems(transport_security_enabled=True)
        assert problems == []
