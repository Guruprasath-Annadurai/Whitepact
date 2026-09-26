# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# mypy: disable-error-code=misc
"""Typed transition semantics (Gate 2 — no unified fake codomain)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

W = TypeVar("W")
Act = TypeVar("Act", contravariant=True)
C = TypeVar("C")
Auth = TypeVar("Auth")
AbsW = TypeVar("AbsW")
Event = TypeVar("Event", contravariant=True)
AuthorityEvent = TypeVar("AuthorityEvent", contravariant=True)


class DeterministicTransition(Protocol[W, Act]):
    def apply(self, world: W, action: Act) -> W: ...


class NondeterministicTransition(Protocol[W, Act]):
    def successors(self, world: W, action: Act) -> frozenset[W]: ...


@dataclass(frozen=True, slots=True)
class ProbabilityMass(Generic[W]):
    """Finite support distribution for probabilistic transitions."""

    masses: tuple[tuple[W, float], ...]

    def __post_init__(self) -> None:
        if not self.masses:
            raise ValueError("empty probability mass is invalid; use a degenerate point mass")
        total = 0.0
        for _, p in self.masses:
            if not math.isfinite(p):
                raise ValueError("probability must be finite")
            if p < 0.0 or p > 1.0:
                raise ValueError("probability out of range [0,1]")
            total += p
        if self.masses and abs(total - 1.0) > 1e-9:
            raise ValueError("probabilities must sum to 1")


class ProbabilisticTransition(Protocol[W, Act]):
    def distribute(self, world: W, action: Act) -> ProbabilityMass[W]: ...


class AbstractTransition(Protocol[AbsW, Act]):
    def step(self, abstract: AbsW, action: Act) -> AbsW: ...


class CapabilityTransition(Protocol[C, Event]):
    def evolve(self, capability: C, event: Event) -> C: ...


class AuthorityTransition(Protocol[Auth, AuthorityEvent]):
    def evolve(self, authority: Auth, event: AuthorityEvent) -> Auth: ...
