# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial tests for Organization Trust Root & Atomic Bootstrap Ceremony."""

from __future__ import annotations

import asyncio

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.trust_fabric.bootstrap import TrustBootstrapManager
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import PrincipalType
from responsibleai.trust_fabric.errors import (
    BootstrapRaceError,
    BootstrapTokenExpiredError,
    BootstrapTokenReplayError,
    CrossTenantAccessError,
    InvalidBootstrapNonceError,
    OrganizationAlreadyBootstrappedError,
    UnauthorizedBootstrapIssuanceError,
)


@pytest.fixture
async def bootstrap_db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path}/test_boot.db"
    engine = create_engine(url)
    await engine.init()
    from responsibleai.db.engine import organizations

    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert(),
            [
                {"id": "org_target", "name": "Target Corp", "slug": "target", "created_at": "now"},
                {"id": "org_other", "name": "Other Corp", "slug": "other", "created_at": "now"},
            ],
        )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.mark.asyncio
class TestTrustBootstrapCeremony:
    async def test_legitimate_bootstrap_ceremony(self, bootstrap_db):
        boot_mgr = TrustBootstrapManager(bootstrap_db)
        dir_svc = PrincipalDirectory(bootstrap_db)

        # 1. Create root human candidate in target org
        alice = await dir_svc.create_principal(
            org_id="org_target",
            principal_type=PrincipalType.HUMAN,
            display_name="Alice Founder",
        )

        # 2. Issue bootstrap ceremony
        token, nonce = await boot_mgr.issue_bootstrap_ceremony(org_id="org_target", ttl_seconds=600)
        assert token.startswith("wp_boot_")
        assert nonce.startswith("nonce_")

        # 3. Claim trust root
        root = await boot_mgr.claim_trust_root(
            org_id="org_target",
            token=token,
            nonce=nonce,
            root_principal_id=alice.id,
            root_public_key="ed25519_pk_abc123",
        )
        assert root.org_id == "org_target"
        assert root.root_principal_id == alice.id
        assert root.status == "ACTIVE"

        # 4. Attempt to bootstrap again fails closed
        with pytest.raises(OrganizationAlreadyBootstrappedError):
            await boot_mgr.issue_bootstrap_ceremony(org_id="org_target")

    async def test_bootstrap_replay_attack_rejected(self, bootstrap_db):
        boot_mgr = TrustBootstrapManager(bootstrap_db)
        dir_svc = PrincipalDirectory(bootstrap_db)

        alice = await dir_svc.create_principal(
            org_id="org_target", principal_type=PrincipalType.HUMAN, display_name="Alice"
        )
        token, nonce = await boot_mgr.issue_bootstrap_ceremony(org_id="org_target")

        # Claim once
        await boot_mgr.claim_trust_root(
            org_id="org_target",
            token=token,
            nonce=nonce,
            root_principal_id=alice.id,
            root_public_key="pk_1",
        )

        # Replay token: BLOCKED
        with pytest.raises((BootstrapTokenReplayError, OrganizationAlreadyBootstrappedError)):
            await boot_mgr.claim_trust_root(
                org_id="org_target",
                token=token,
                nonce=nonce,
                root_principal_id=alice.id,
                root_public_key="pk_replay",
            )

    async def test_bootstrap_expired_token_rejected(self, bootstrap_db):
        boot_mgr = TrustBootstrapManager(bootstrap_db)
        dir_svc = PrincipalDirectory(bootstrap_db)

        alice = await dir_svc.create_principal(
            org_id="org_target", principal_type=PrincipalType.HUMAN, display_name="Alice"
        )
        # Issue ceremony with -10 second TTL (already expired)
        token, nonce = await boot_mgr.issue_bootstrap_ceremony(org_id="org_target", ttl_seconds=-10)

        with pytest.raises(BootstrapTokenExpiredError):
            await boot_mgr.claim_trust_root(
                org_id="org_target",
                token=token,
                nonce=nonce,
                root_principal_id=alice.id,
                root_public_key="pk_1",
            )

    async def test_cross_tenant_bootstrap_rejected(self, bootstrap_db):
        boot_mgr = TrustBootstrapManager(bootstrap_db)
        dir_svc = PrincipalDirectory(bootstrap_db)

        # Alice belongs to org_other, not org_target
        alice_other = await dir_svc.create_principal(
            org_id="org_other", principal_type=PrincipalType.HUMAN, display_name="Foreign Alice"
        )
        token, nonce = await boot_mgr.issue_bootstrap_ceremony(org_id="org_target")

        # Alice from org_other attempts to claim root of org_target: BLOCKED
        with pytest.raises(CrossTenantAccessError):
            await boot_mgr.claim_trust_root(
                org_id="org_target",
                token=token,
                nonce=nonce,
                root_principal_id=alice_other.id,
                root_public_key="pk_foreign",
            )

        # Token stolen from org_target used against org_other: BLOCKED
        with pytest.raises(InvalidBootstrapNonceError):
            await boot_mgr.claim_trust_root(
                org_id="org_other",
                token=token,
                nonce=nonce,
                root_principal_id=alice_other.id,
                root_public_key="pk_foreign",
            )

    async def test_concurrent_bootstrap_race_single_winner(self, bootstrap_db):
        """Under concurrent execution race, exactly ONE root winner succeeds."""
        boot_mgr = TrustBootstrapManager(bootstrap_db)
        dir_svc = PrincipalDirectory(bootstrap_db)

        alice = await dir_svc.create_principal(
            org_id="org_target", principal_type=PrincipalType.HUMAN, display_name="Alice"
        )
        token, nonce = await boot_mgr.issue_bootstrap_ceremony(org_id="org_target")

        async def _attempt_bootstrap(idx: int):
            try:
                await boot_mgr.claim_trust_root(
                    org_id="org_target",
                    token=token,
                    nonce=nonce,
                    root_principal_id=alice.id,
                    root_public_key=f"pk_race_{idx}",
                )
                return "WINNER"
            except (
                OrganizationAlreadyBootstrappedError,
                BootstrapRaceError,
                BootstrapTokenReplayError,
            ):
                return "LOST_RACE"

        results = await asyncio.gather(*[_attempt_bootstrap(i) for i in range(25)])

        assert results.count("WINNER") == 1
        assert results.count("LOST_RACE") == 24

        # Verify only 1 root exists in DB
        root = await boot_mgr.get_trust_root(org_id="org_target")
        assert root is not None

    async def test_unauthorized_token_issuance_defense(self, bootstrap_db):
        """Ordinary users and cross-tenant callers cannot issue bootstrap tokens."""
        boot_mgr = TrustBootstrapManager(bootstrap_db)
        dir_svc = PrincipalDirectory(bootstrap_db)

        founder = await dir_svc.create_principal(
            org_id="org_target",
            principal_type=PrincipalType.HUMAN,
            display_name="Target Founder",
            metadata={"is_organization_creator": True, "role": "ORGANIZATION_FOUNDER"},
        )
        ordinary_user = await dir_svc.create_principal(
            org_id="org_target",
            principal_type=PrincipalType.HUMAN,
            display_name="Ordinary Employee",
            metadata={"role": "MEMBER"},
        )
        foreign_admin = await dir_svc.create_principal(
            org_id="org_other",
            principal_type=PrincipalType.HUMAN,
            display_name="Foreign Admin",
            metadata={"is_organization_creator": True, "role": "ORGANIZATION_FOUNDER"},
        )

        # 1. Ordinary member attempts to issue: REJECTED
        with pytest.raises(UnauthorizedBootstrapIssuanceError):
            await boot_mgr.issue_bootstrap_ceremony(
                org_id="org_target",
                caller_principal_id=ordinary_user.id,
            )

        # 2. Foreign admin of another org attempts to issue: REJECTED (cross-tenant)
        with pytest.raises(CrossTenantAccessError):
            await boot_mgr.issue_bootstrap_ceremony(
                org_id="org_target",
                caller_principal_id=foreign_admin.id,
            )

        # 3. Legitimate founder issues: ACCEPTED
        token, nonce = await boot_mgr.issue_bootstrap_ceremony(
            org_id="org_target",
            caller_principal_id=founder.id,
        )
        assert token.startswith("wp_boot_")

    async def test_platform_operator_backdoor_blocked(self, bootstrap_db):
        """WhitePact platform operators cannot silently inject customer roots."""
        boot_mgr = TrustBootstrapManager(bootstrap_db)

        with pytest.raises(UnauthorizedBootstrapIssuanceError):
            await boot_mgr.issue_bootstrap_ceremony(
                org_id="org_target",
                caller_principal_id="whitepact_operator",
            )

        with pytest.raises(UnauthorizedBootstrapIssuanceError):
            await boot_mgr.issue_bootstrap_ceremony(
                org_id="org_target",
                caller_principal_id="operator_backdoor",
            )

    async def test_token_principal_binding_enforced(self, bootstrap_db):
        """A bootstrap token bound to Alice cannot be redeemed by Bob (separation of duties)."""
        boot_mgr = TrustBootstrapManager(bootstrap_db)
        dir_svc = PrincipalDirectory(bootstrap_db)

        alice = await dir_svc.create_principal(
            org_id="org_target",
            principal_type=PrincipalType.HUMAN,
            display_name="Alice Founder",
            metadata={"is_organization_creator": True},
        )
        bob = await dir_svc.create_principal(
            org_id="org_target",
            principal_type=PrincipalType.HUMAN,
            display_name="Bob Imposter",
        )

        token, nonce = await boot_mgr.issue_bootstrap_ceremony(
            org_id="org_target",
            caller_principal_id=alice.id,
            authorized_redeemer_principal_id=alice.id,
        )

        # Bob attempts to redeem Alice's token: REJECTED
        with pytest.raises(UnauthorizedBootstrapIssuanceError):
            await boot_mgr.claim_trust_root(
                org_id="org_target",
                token=token,
                nonce=nonce,
                root_principal_id=bob.id,
                root_public_key="ed25519_pk_bob",
            )

        # Alice redeems: ACCEPTED
        root = await boot_mgr.claim_trust_root(
            org_id="org_target",
            token=token,
            nonce=nonce,
            root_principal_id=alice.id,
            root_public_key="ed25519_pk_alice",
        )
        assert root.root_principal_id == alice.id
