# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Delegation Graph as a first-class object (Authority
Everywhere Phase 6) -- `governance/delegation_graph.py`'s
`DelegationGraph`/`DelegationGraphNode`, and
`db/delegation_repository.py`'s new `get_org_graph()`/`get_descendants()`.

Separate from `tests/test_delegation_graph.py`, which already existed
(pre-dating this phase) and covers the base delegation graph:
`grant()`, attenuation enforcement, `get_authority_chain()`,
`revoke_branch()`, `explain_authority()`. This file covers only the
new org-wide forest/descendants queries this phase adds.
"""

from __future__ import annotations

from responsibleai.db import DelegationRepository, create_engine
from responsibleai.governance.delegation_graph import DelegationGraph, DelegationGraphNode


async def _engine():
    engine = create_engine(":memory:")
    await engine.init()
    return engine


async def _build_tree(repo: DelegationRepository) -> None:
    """org-1: manager-1 (root) -> agent-1 -> subagent-1
    org-1: manager-2 (a second, independent root, no children)"""
    await repo.grant(
        "org-1",
        "manager-1",
        granted_action_types=frozenset({"rai_scan"}),
        purpose="root",
        granted_by="admin",
    )
    await repo.grant(
        "org-1",
        "agent-1",
        from_identity_id="manager-1",
        granted_action_types=frozenset({"rai_scan"}),
        purpose="delegated",
        granted_by="manager-1",
    )
    await repo.grant(
        "org-1",
        "subagent-1",
        from_identity_id="agent-1",
        granted_action_types=frozenset({"rai_scan"}),
        purpose="sub-delegated",
        granted_by="agent-1",
    )
    await repo.grant(
        "org-1",
        "manager-2",
        granted_action_types=frozenset({"rai_scan"}),
        purpose="second root",
        granted_by="admin",
    )


class TestDelegationGraphNode:
    def test_is_active_true_when_delegation_active(self) -> None:
        from datetime import UTC, datetime

        from responsibleai.governance.delegation import DelegationRecord

        record = DelegationRecord(
            delegation_id="d1",
            org_id="org-1",
            from_identity_id=None,
            to_identity_id="agent-1",
            granted_action_types=frozenset({"rai_scan"}),
            constraints={},
            require_approval_for=frozenset(),
            purpose="test",
            granted_by="admin",
            granted_at=datetime.now(UTC),
        )
        node = DelegationGraphNode(identity_id="agent-1", delegation=record)
        assert node.is_active() is True

    def test_is_active_false_when_no_delegation(self) -> None:
        node = DelegationGraphNode(identity_id="agent-1", delegation=None)
        assert node.is_active() is False

    def test_descendant_count(self) -> None:
        leaf = DelegationGraphNode(identity_id="c", delegation=None)
        mid = DelegationGraphNode(identity_id="b", delegation=None, children=(leaf,))
        root = DelegationGraphNode(identity_id="a", delegation=None, children=(mid,))
        assert root.descendant_count() == 2


class TestDelegationGraph:
    def test_all_identity_ids(self) -> None:
        leaf = DelegationGraphNode(identity_id="c", delegation=None)
        mid = DelegationGraphNode(identity_id="b", delegation=None, children=(leaf,))
        root = DelegationGraphNode(identity_id="a", delegation=None, children=(mid,))
        graph = DelegationGraph(organization_id="org-1", roots=(root,))
        assert graph.all_identity_ids() == {"a", "b", "c"}

    def test_find_locates_nested_node(self) -> None:
        leaf = DelegationGraphNode(identity_id="c", delegation=None)
        mid = DelegationGraphNode(identity_id="b", delegation=None, children=(leaf,))
        root = DelegationGraphNode(identity_id="a", delegation=None, children=(mid,))
        graph = DelegationGraph(organization_id="org-1", roots=(root,))
        assert graph.find("c") is leaf
        assert graph.find("does-not-exist") is None

    def test_to_dict_shape(self) -> None:
        leaf = DelegationGraphNode(identity_id="c", delegation=None)
        root = DelegationGraphNode(identity_id="a", delegation=None, children=(leaf,))
        graph = DelegationGraph(organization_id="org-1", roots=(root,))
        d = graph.to_dict()
        assert d["organization_id"] == "org-1"
        assert d["root_count"] == 1
        assert d["total_identity_count"] == 2
        assert len(d["roots"]) == 1
        assert len(d["roots"][0]["children"]) == 1


class TestGetOrgGraph:
    async def test_builds_multi_level_multi_root_forest(self) -> None:
        engine = await _engine()
        try:
            repo = DelegationRepository(engine)
            await _build_tree(repo)
            graph = await repo.get_org_graph("org-1")
            assert len(graph.roots) == 2
            assert graph.all_identity_ids() == {"manager-1", "agent-1", "subagent-1", "manager-2"}

            manager1 = graph.find("manager-1")
            assert manager1 is not None
            assert len(manager1.children) == 1
            assert manager1.children[0].identity_id == "agent-1"
            assert manager1.children[0].children[0].identity_id == "subagent-1"

            manager2 = graph.find("manager-2")
            assert manager2 is not None
            assert manager2.children == ()
        finally:
            await engine.close()

    async def test_empty_org_returns_empty_graph(self) -> None:
        engine = await _engine()
        try:
            repo = DelegationRepository(engine)
            graph = await repo.get_org_graph("org-with-nothing")
            assert graph.roots == ()
            assert graph.all_identity_ids() == set()
        finally:
            await engine.close()

    async def test_revocation_reflected_in_graph(self) -> None:
        engine = await _engine()
        try:
            repo = DelegationRepository(engine)
            await _build_tree(repo)
            await repo.revoke_branch("org-1", "manager-1", revoked_by="admin", reason="test")
            graph = await repo.get_org_graph("org-1")

            manager1 = graph.find("manager-1")
            agent1 = graph.find("agent-1")
            subagent1 = graph.find("subagent-1")
            manager2 = graph.find("manager-2")
            assert manager1 is not None and manager1.is_active() is False
            assert agent1 is not None and agent1.is_active() is False
            assert subagent1 is not None and subagent1.is_active() is False
            # revoking manager-1's branch must never touch the independent manager-2 root
            assert manager2 is not None and manager2.is_active() is True
        finally:
            await engine.close()

    async def test_re_delegation_under_new_parent_moves_node(self) -> None:
        """An identity re-granted from a different parent shows up
        under its *current* parent only -- not duplicated, not left
        under the stale original parent."""
        engine = await _engine()
        try:
            repo = DelegationRepository(engine)
            await repo.grant(
                "org-1",
                "manager-1",
                granted_action_types=frozenset({"rai_scan"}),
                purpose="root a",
                granted_by="admin",
            )
            await repo.grant(
                "org-1",
                "manager-2",
                granted_action_types=frozenset({"rai_scan"}),
                purpose="root b",
                granted_by="admin",
            )
            await repo.grant(
                "org-1",
                "agent-1",
                from_identity_id="manager-1",
                granted_action_types=frozenset({"rai_scan"}),
                purpose="under manager-1",
                granted_by="manager-1",
            )
            # re-grant agent-1 from manager-2 instead
            await repo.grant(
                "org-1",
                "agent-1",
                from_identity_id="manager-2",
                granted_action_types=frozenset({"rai_scan"}),
                purpose="under manager-2 now",
                granted_by="manager-2",
            )

            graph = await repo.get_org_graph("org-1")
            manager1 = graph.find("manager-1")
            manager2 = graph.find("manager-2")
            assert manager1 is not None and manager1.children == ()
            assert manager2 is not None
            assert len(manager2.children) == 1
            assert manager2.children[0].identity_id == "agent-1"
        finally:
            await engine.close()


class TestGetDescendants:
    async def test_returns_transitive_descendants(self) -> None:
        engine = await _engine()
        try:
            repo = DelegationRepository(engine)
            await _build_tree(repo)
            descendants = await repo.get_descendants("org-1", "manager-1")
            ids = {d.to_identity_id for d in descendants}
            assert ids == {"agent-1", "subagent-1"}
        finally:
            await engine.close()

    async def test_leaf_identity_has_no_descendants(self) -> None:
        engine = await _engine()
        try:
            repo = DelegationRepository(engine)
            await _build_tree(repo)
            descendants = await repo.get_descendants("org-1", "subagent-1")
            assert descendants == []
        finally:
            await engine.close()

    async def test_never_granted_identity_has_no_descendants(self) -> None:
        engine = await _engine()
        try:
            repo = DelegationRepository(engine)
            descendants = await repo.get_descendants("org-1", "never-existed")
            assert descendants == []
        finally:
            await engine.close()
