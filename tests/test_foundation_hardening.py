# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Foundation hardening regressions.

Covers confirmed defects: authority HTTPS egress allowlist, policy
shadowing, evidence-head witnesses, and organization-scoped rate-limit
keys. Positive cases are included beside the rejected ones.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from starlette.requests import Request

from responsibleai.dashboard.app import _get_rate_limit_key
from responsibleai.db import PolicyRepository, create_engine
from responsibleai.governance.evidence_witness import (
    LIVE_ANCHOR_STATUS,
    EvidenceWitnessError,
    sign_evidence_head,
    verify_evidence_head,
)
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import (
    PolicyRule,
    PolicyShadowError,
    reject_shadowed_restrictive_rules,
)
from responsibleai.governance.policy_lifecycle import PolicyLifecycleManager
from responsibleai.governance.risk import RiskTier

ROOT = Path(__file__).resolve().parents[1]
LOCALS = ROOT / "infra" / "terraform" / "modules" / "whitepact-hetzner-foundation" / "locals.tf"


def test_authority_nft_output_has_no_unrestricted_https_accept() -> None:
    text = LOCALS.read_text(encoding="utf-8")
    assert 'tcp dport 443 accept comment "R2 backup upload via NAT"' not in text
    assert "authority_egress_cidrs" in text
    start = text.index("authority_nft_output")
    block = text[start : text.index("execution_nft_output")]
    assert "tcp dport 443 accept" not in block
    assert "ip daddr" in block


def test_specific_allow_before_broad_deny_is_not_a_shadow() -> None:
    rules = [
        PolicyRule(
            rule_id="allow-read",
            reason_code="ok",
            effect=GovernanceDecision.ALLOW,
            action_types=frozenset({"rai_health"}),
        ),
        PolicyRule(
            rule_id="deny-rest",
            reason_code="no",
            effect=GovernanceDecision.DENY,
        ),
    ]
    reject_shadowed_restrictive_rules(rules)


def test_broad_allow_shadowing_later_deny_is_rejected() -> None:
    rules = [
        PolicyRule(rule_id="allow-all", reason_code="ok", effect=GovernanceDecision.ALLOW),
        PolicyRule(
            rule_id="deny-payment",
            reason_code="no",
            effect=GovernanceDecision.DENY,
            action_types=frozenset({"payment.transfer"}),
        ),
    ]
    with pytest.raises(PolicyShadowError, match="deny-payment"):
        reject_shadowed_restrictive_rules(rules)


@pytest.fixture()
async def policy_repo():
    engine = create_engine(":memory:")
    await engine.init()
    yield PolicyRepository(engine)
    await engine.close()


async def test_repository_refuses_to_persist_shadowed_deny(policy_repo: PolicyRepository) -> None:
    await policy_repo.add_rule(
        "org-1",
        PolicyRule(rule_id="allow-all", reason_code="ok", effect=GovernanceDecision.ALLOW),
    )
    with pytest.raises(PolicyShadowError):
        await policy_repo.add_rule(
            "org-1",
            PolicyRule(
                rule_id="deny-payment",
                reason_code="no",
                effect=GovernanceDecision.DENY,
                action_types=frozenset({"payment.transfer"}),
            ),
        )
    policy = await policy_repo.get_policy("org-1")
    assert [rule.rule_id for rule in policy.rules] == ["allow-all"]


async def test_repository_keeps_legitimate_descendant_exception(
    policy_repo: PolicyRepository,
) -> None:
    await policy_repo.add_rule(
        "org-1",
        PolicyRule(
            rule_id="deny-payment",
            reason_code="no",
            effect=GovernanceDecision.DENY,
            action_types=frozenset({"payment.transfer"}),
            risk_tiers=frozenset({RiskTier.HIGH}),
        ),
    )
    await policy_repo.add_rule(
        "org-1",
        PolicyRule(
            rule_id="allow-read",
            reason_code="ok",
            effect=GovernanceDecision.ALLOW,
            action_types=frozenset({"rai_health"}),
        ),
    )
    policy = await policy_repo.get_policy("org-1")
    assert [rule.rule_id for rule in policy.rules] == ["deny-payment", "allow-read"]


async def test_lifecycle_refuses_shadowed_revision() -> None:
    engine = create_engine(":memory:")
    await engine.init()
    org_id = f"org-{uuid.uuid4().hex[:8]}"
    async with engine.raw.begin() as conn:
        from sqlalchemy import insert

        from responsibleai.db.engine import organizations

        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Shadow Org",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-10-09T00:00:00Z",
            )
        )
    manager = PolicyLifecycleManager(engine)
    with pytest.raises(PolicyShadowError):
        await manager.create_revision(
            org_id,
            [
                PolicyRule(rule_id="allow-all", reason_code="ok", effect=GovernanceDecision.ALLOW),
                PolicyRule(rule_id="deny-rest", reason_code="no", effect=GovernanceDecision.DENY),
            ],
            "admin",
            "attempted shadow",
        )
    await engine.close()


def test_evidence_witness_binds_head_and_rejects_recomputed_rewrite() -> None:
    assert LIVE_ANCHOR_STATUS == "EXTERNAL_BLOCKER"
    key = Ed25519PrivateKey.generate()
    witness = sign_evidence_head(
        key,
        organization_id="org-1",
        chain_sequence=4,
        head_hash="a" * 64,
        witnessed_at="2026-10-09T00:00:00+00:00",
    )
    assert verify_evidence_head(
        witness,
        organization_id="org-1",
        chain_sequence=4,
        head_hash="a" * 64,
    )
    rewritten = "b" * 64
    with pytest.raises(EvidenceWitnessError, match="head hash"):
        verify_evidence_head(
            witness,
            organization_id="org-1",
            chain_sequence=4,
            head_hash=rewritten,
        )


def test_evidence_witness_rejects_a_different_signing_key() -> None:
    witness = sign_evidence_head(
        Ed25519PrivateKey.generate(),
        organization_id="org-1",
        chain_sequence=1,
        head_hash="c" * 64,
        witnessed_at="2026-10-09T00:00:00+00:00",
    )
    other = Ed25519PrivateKey.generate().public_key().public_bytes_raw().hex()
    forged = type(witness)(
        organization_id=witness.organization_id,
        chain_sequence=witness.chain_sequence,
        head_hash=witness.head_hash,
        witnessed_at=witness.witnessed_at,
        public_key_hex=other,
        signature_hex=witness.signature_hex,
    )
    with pytest.raises(EvidenceWitnessError, match="signature"):
        verify_evidence_head(
            forged,
            organization_id="org-1",
            chain_sequence=1,
            head_hash="c" * 64,
        )


def _request(authorization: str, org_id: str | None) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/evaluate",
        "raw_path": b"/api/evaluate",
        "query_string": b"",
        "headers": [(b"authorization", authorization.encode())],
        "client": ("198.51.100.20", 443),
        "server": ("test", 80),
    }
    request = Request(scope)
    if org_id is not None:
        request.state.audit_org_id = org_id
    return request


def test_rate_limit_key_is_org_scoped_across_rotated_tokens() -> None:
    first = _get_rate_limit_key(_request("Bearer token-one", "org-a"))
    second = _get_rate_limit_key(_request("Bearer token-two", "org-a"))
    other = _get_rate_limit_key(_request("Bearer token-one", "org-b"))
    assert first == second == "org:org-a"
    assert other == "org:org-b"


def test_production_multi_replica_without_shared_backends_refuses_start() -> None:
    from responsibleai.dashboard.config import (
        enforce_shared_backends_for_multi_replica,
        multi_replica_problems,
    )

    problems = multi_replica_problems("sqlite", "memory")
    assert problems
    with pytest.raises(RuntimeError, match="multi-replica"):
        enforce_shared_backends_for_multi_replica(production=True, problems=problems)
    enforce_shared_backends_for_multi_replica(production=False, problems=problems)
    enforce_shared_backends_for_multi_replica(
        production=True,
        problems=multi_replica_problems("postgresql", "redis"),
    )
    lifespan = (ROOT / "src" / "responsibleai" / "dashboard" / "app.py").read_text(encoding="utf-8")
    assert "enforce_shared_backends_for_multi_replica" in lifespan


def test_unauthenticated_rate_limit_key_stays_per_token_until_org_resolves() -> None:
    first = _get_rate_limit_key(_request("Bearer token-one", None))
    second = _get_rate_limit_key(_request("Bearer token-two", None))
    assert first.startswith("key:")
    assert first != second


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def _sudo() -> list[str]:
    if os.geteuid() == 0:
        return []
    if shutil.which("sudo") is None:
        pytest.fail("sudo is required to load nftables in a network namespace")
    return ["sudo", "-n"]


def _nft_script(table: str, extra_accept: str) -> str:
    return f"""
table inet {table} {{
  counter allowlisted {{}}
  counter unrestricted {{}}
  chain output {{
    type filter hook output priority 0; policy drop;
    tcp dport 443 ip daddr 10.255.0.1 counter name allowlisted accept
    {extra_accept}
  }}
}}
"""


def _counter_packets(listing: str, name: str) -> int:
    lines = listing.splitlines()
    for index, line in enumerate(lines):
        if f"counter {name}" not in line:
            continue
        window = "\n".join(lines[index : index + 4])
        marker = "packets "
        start = window.find(marker)
        if start < 0:
            return 0
        number = window[start + len(marker) :].split()[0]
        return int(number)
    return 0


def _send_https(ns: str, destination: str) -> None:
    prefix = [*_sudo(), "ip", "netns", "exec", ns]
    _run(
        [
            *prefix,
            "python3",
            "-c",
            (
                "import socket; s=socket.socket(); s.settimeout(0.2);\n"
                "try:\n"
                f"    s.connect(('{destination}', 443))\n"
                "except OSError:\n"
                "    pass\n"
            ),
        ]
    )


def _load_table(ns: str, path: Path) -> None:
    loaded = _run([*_sudo(), "ip", "netns", "exec", ns, "nft", "-f", str(path)])
    if loaded.returncode != 0:
        pytest.fail(loaded.stderr or loaded.stdout)


def test_isolated_nft_authority_https_allowlist() -> None:
    """Reproduce the effective output policy in a network namespace.

    The historical NAT backup rule accepted every TCP/443 destination.
    The remediated chain accepts only the backup allowlist.
    """
    if shutil.which("nft") is None or shutil.which("ip") is None:
        pytest.fail("nft and ip are required to reproduce the egress policy")
    prefix = _sudo()
    ns = f"wp-egress-{uuid.uuid4().hex[:8]}"
    created = _run([*prefix, "ip", "netns", "add", ns])
    if created.returncode != 0:
        pytest.fail(created.stderr or created.stdout)
    try:
        setup = [
            [*prefix, "ip", "netns", "exec", ns, "ip", "link", "set", "lo", "up"],
            [
                *prefix,
                "ip",
                "netns",
                "exec",
                ns,
                "ip",
                "link",
                "add",
                "veth0",
                "type",
                "veth",
                "peer",
                "name",
                "veth1",
            ],
            [*prefix, "ip", "netns", "exec", ns, "ip", "link", "set", "veth0", "up"],
            [*prefix, "ip", "netns", "exec", ns, "ip", "link", "set", "veth1", "up"],
            [
                *prefix,
                "ip",
                "netns",
                "exec",
                ns,
                "ip",
                "route",
                "add",
                "10.255.0.1/32",
                "dev",
                "veth0",
            ],
            [
                *prefix,
                "ip",
                "netns",
                "exec",
                ns,
                "ip",
                "route",
                "add",
                "203.0.113.10/32",
                "dev",
                "veth0",
            ],
        ]
        for cmd in setup:
            result = _run(cmd)
            if result.returncode != 0:
                pytest.fail(result.stderr or result.stdout)

        broken = Path(f"/tmp/{ns}-broken.nft")
        fixed = Path(f"/tmp/{ns}-fixed.nft")
        broken.write_text(
            _nft_script("wp_broken", "tcp dport 443 counter name unrestricted accept"),
            encoding="utf-8",
        )
        fixed.write_text(_nft_script("wp_fixed", ""), encoding="utf-8")
        _load_table(ns, broken)
        _send_https(ns, "203.0.113.10")
        broken_list = _run(
            [*prefix, "ip", "netns", "exec", ns, "nft", "list", "table", "inet", "wp_broken"]
        )
        assert _counter_packets(broken_list.stdout, "unrestricted") >= 1
        assert _counter_packets(broken_list.stdout, "allowlisted") == 0
        deleted = _run(
            [*prefix, "ip", "netns", "exec", ns, "nft", "delete", "table", "inet", "wp_broken"]
        )
        if deleted.returncode != 0:
            pytest.fail(deleted.stderr or deleted.stdout)

        _load_table(ns, fixed)
        _send_https(ns, "203.0.113.10")
        outside = _run(
            [*prefix, "ip", "netns", "exec", ns, "nft", "list", "table", "inet", "wp_fixed"]
        )
        assert _counter_packets(outside.stdout, "allowlisted") == 0
        _send_https(ns, "10.255.0.1")
        backup = _run(
            [*prefix, "ip", "netns", "exec", ns, "nft", "list", "table", "inet", "wp_fixed"]
        )
        assert _counter_packets(backup.stdout, "allowlisted") >= 1
    finally:
        _run([*prefix, "ip", "netns", "del", ns])
