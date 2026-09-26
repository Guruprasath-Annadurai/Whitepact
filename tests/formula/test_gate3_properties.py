# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from tests.formula.helpers_gate3 import build_snapshot, edge, node

from responsibleai.formula.capability import compute_capability_closure
from responsibleai.formula.capability.serialize import serialize_closure_result
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind
from responsibleai.formula.serialization import canonical_sha256


def test_closure_idempotent() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL), node("db", NodeKind.DATABASE)),
        edges=(
            edge("e1", EdgeKind.CAN_CALL, "a", "t"),
            edge("e2", EdgeKind.CAN_WRITE, "t", "db"),
        ),
    )
    once = compute_capability_closure(snap)
    twice = compute_capability_closure(snap, seeds=once.facts)
    assert {f.semantic_key() for f in once.facts} == {f.semantic_key() for f in twice.facts}


def test_seed_inclusion() -> None:
    snap = build_snapshot(nodes=(node("a", NodeKind.AGENT),))
    once = compute_capability_closure(snap)
    twice = compute_capability_closure(snap, seeds=once.facts)
    for k in {f.semantic_key() for f in once.facts}:
        assert k in {f.semantic_key() for f in twice.facts}


def test_order_independence() -> None:
    snap1 = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_CALL, "a", "t"),),
    )
    snap2 = build_snapshot(
        nodes=(node("t", NodeKind.TOOL), node("a", NodeKind.AGENT)),
        edges=(edge("e1", EdgeKind.CAN_CALL, "a", "t"),),
    )
    h1 = canonical_sha256(serialize_closure_result(compute_capability_closure(snap1)))
    h2 = canonical_sha256(serialize_closure_result(compute_capability_closure(snap2)))
    assert h1 == h2
