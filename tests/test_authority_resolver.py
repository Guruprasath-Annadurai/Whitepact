"""Tests for Heart Production Integration Phase 5 (Authority Resolver).
See docs/heart-production/04_AUTHORITY_RESOLVER.md.

Covers get-or-create root resolution, chain prefetching (linear,
cycle-safe, missing-source, depth-bound), and `resolve_authority_grant()`
end-to-end against a real (`:memory:`) `RootAuthorityRepository` for
both a terminal identity (immediately legitimate) and a non-terminal
one with no resolvable source (correctly NOT legitimate -- proving
this resolver actually asks Heart Phase H3's question, not just
plumbs data through unchecked).
"""

from __future__ import annotations

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.root_authority_repository import RootAuthorityRepository
from responsibleai.governance.authority_resolver import (
    prefetch_root_chain,
    resolve_authority_grant,
    resolve_root_for_identity,
)
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    IdentityContext,
)
from responsibleai.governance.root_authority import RootType, build_root_authority_record


@pytest.fixture()
async def db():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def root_repo(db):
    return RootAuthorityRepository(db)


class TestResolveRootForIdentityGetOrCreate:
    async def test_creates_a_new_root_when_none_exists(self, root_repo):
        identity = IdentityContext(identity_id="user-1", kind="api_key", org_id="org-1")
        root = await resolve_root_for_identity(
            identity, root_repo, issuer="org_repository", verification_method="api_key_hash"
        )
        assert root.subject_id == "user-1"
        assert root.root_type == RootType.ORGANIZATION

        fetched = await root_repo.get(root.root_id)
        assert fetched is not None

    async def test_reuses_the_existing_root_rather_than_creating_a_second(self, root_repo):
        identity = IdentityContext(identity_id="user-1", kind="api_key", org_id="org-1")
        first = await resolve_root_for_identity(
            identity, root_repo, issuer="org_repository", verification_method="api_key_hash"
        )
        second = await resolve_root_for_identity(
            identity, root_repo, issuer="org_repository", verification_method="api_key_hash"
        )
        assert first.root_id == second.root_id

    async def test_a_revoked_root_is_returned_as_is_not_silently_replaced(self, root_repo):
        """Fail-closed: re-issuing a fresh root for a revoked identity
        would silently bypass the revocation."""
        identity = IdentityContext(identity_id="user-1", kind="api_key", org_id="org-1")
        root = await resolve_root_for_identity(
            identity, root_repo, issuer="org_repository", verification_method="api_key_hash"
        )
        revoked = await root_repo.revoke(root.root_id, revoked_by="admin", reason="offboarded")

        again = await resolve_root_for_identity(
            identity, root_repo, issuer="org_repository", verification_method="api_key_hash"
        )
        assert again.root_id == revoked.root_id
        assert again.revoked_at is not None


class TestPrefetchRootChain:
    async def test_linear_chain_is_fully_prefetched(self, root_repo):
        org_root = build_root_authority_record("org-1", RootType.ORGANIZATION, "idp", "oidc")
        await root_repo.create(org_root)
        service_root = build_root_authority_record(
            "svc-1",
            RootType.SERVICE_PRINCIPAL,
            "internal",
            "mtls",
            authority_source=org_root.root_id,
        )
        await root_repo.create(service_root)

        prefetched = await prefetch_root_chain(service_root, root_repo)
        assert set(prefetched) == {service_root.root_id, org_root.root_id}

    async def test_missing_source_stops_the_walk_without_raising(self, root_repo):
        service_root = build_root_authority_record(
            "svc-1",
            RootType.SERVICE_PRINCIPAL,
            "internal",
            "mtls",
            authority_source="does-not-exist",
        )
        await root_repo.create(service_root)

        prefetched = await prefetch_root_chain(service_root, root_repo)
        assert set(prefetched) == {service_root.root_id}

    async def test_terminal_root_has_no_further_walk(self, root_repo):
        org_root = build_root_authority_record("org-1", RootType.ORGANIZATION, "idp", "oidc")
        await root_repo.create(org_root)

        prefetched = await prefetch_root_chain(org_root, root_repo)
        assert set(prefetched) == {org_root.root_id}

    async def test_cycle_does_not_infinite_loop(self, root_repo):
        """A -> B -> A: build_root_authority_record()'s constructor
        always generates a fresh root_id, so a real self-referential
        cycle needs both records persisted first, then B's
        authority_source patched to point back at A after the fact --
        simulated here via two independently created records that
        happen to reference each other."""
        record_a = build_root_authority_record(
            "a", RootType.SERVICE_PRINCIPAL, "iss", "m", authority_source="b-id"
        )
        record_b = build_root_authority_record(
            "b", RootType.SERVICE_PRINCIPAL, "iss", "m", authority_source=record_a.root_id
        )
        # Overwrite record_a's authority_source to point at b's real id,
        # forming an actual cycle a -> b -> a.
        import dataclasses

        record_a = dataclasses.replace(record_a, authority_source=record_b.root_id)
        await root_repo.create(record_a)
        await root_repo.create(record_b)

        prefetched = await prefetch_root_chain(record_a, root_repo)
        assert set(prefetched) == {record_a.root_id, record_b.root_id}


def _identity(kind: str = "api_key", identity_id: str = "user-1") -> IdentityContext:
    return IdentityContext(identity_id=identity_id, kind=kind, org_id="org-1")


def _agent(identity: IdentityContext) -> AgentContext:
    return AgentContext(identity=identity, organization_id="org-1", agent_id="agent-1")


def _action(agent: AgentContext) -> ActionRequest:
    return ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_scan")


class TestResolveAuthorityGrantEndToEnd:
    async def test_terminal_identity_produces_an_immediately_legitimate_grant(self, root_repo):
        """kind="api_key" maps to RootType.ORGANIZATION, a terminal
        root type -- no authority_source needed, so the grant's
        legitimacy is valid on the first resolution."""
        identity = _identity(kind="api_key")
        agent = _agent(identity)
        action = _action(agent)
        authority_context = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"})
        )

        grant = await resolve_authority_grant(
            identity,
            agent,
            action,
            authority_context,
            root_repo,
            issuer="org_repository",
            verification_method="api_key_hash",
        )
        assert grant.is_legitimate is True
        assert grant.root_reference is not None
        assert grant.principal_id == "user-1"
        assert grant.requested_action_type == "mcp_tool_call"

    async def test_non_terminal_identity_with_no_source_is_not_legitimate(self, root_repo):
        """kind="oidc" maps to RootType.WORKLOAD_IDENTITY, non-terminal
        -- with no authority_source supplied, validate_root_chain()
        reports ROOT_TYPE_CANNOT_SELF_ORIGINATE, which must propagate
        all the way through conflict resolution and the Heart veto to
        an actually-not-legitimate grant. This is the property that
        proves this resolver asks a real question, not a rubber stamp."""
        identity = _identity(kind="oidc", identity_id="oidc:sub123")
        agent = _agent(identity)
        action = _action(agent)
        authority_context = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"})
        )

        grant = await resolve_authority_grant(
            identity,
            agent,
            action,
            authority_context,
            root_repo,
            issuer="idp",
            verification_method="oidc",
        )
        assert grant.is_legitimate is False
        assert grant.legitimacy.heart_veto.is_vetoed is True

    async def test_effective_authority_reflects_the_supplied_authority_context(self, root_repo):
        identity = _identity()
        agent = _agent(identity)
        action = _action(agent)
        authority_context = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"mcp_tool_call"}),
            constraints={"max_value_usd": 100.0},
        )

        grant = await resolve_authority_grant(
            identity,
            agent,
            action,
            authority_context,
            root_repo,
            issuer="org_repository",
            verification_method="api_key_hash",
        )
        assert grant.effective_authority.action_types == frozenset({"mcp_tool_call"})
        assert grant.effective_authority.max_value == 100.0

    async def test_unrepresentable_constraint_raises_rather_than_silently_dropping(self, root_repo):
        from responsibleai.governance.authority_lattice import UnrepresentableConstraintError

        identity = _identity()
        agent = _agent(identity)
        action = _action(agent)
        authority_context = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"mcp_tool_call"}),
            constraints={"memory_scope": "session"},
        )

        with pytest.raises(UnrepresentableConstraintError):
            await resolve_authority_grant(
                identity,
                agent,
                action,
                authority_context,
                root_repo,
                issuer="org_repository",
                verification_method="api_key_hash",
            )
