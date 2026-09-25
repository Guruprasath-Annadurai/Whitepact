# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.authority.algebra import authority_subset, validate_delegation
from responsibleai.formula.authority.models import AuthorityGrant
from responsibleai.formula.errors import InvalidDelegation


@dataclass(frozen=True, slots=True)
class DelegationChain:
    grants: tuple[AuthorityGrant, ...]

    def validate(self) -> None:
        for i in range(1, len(self.grants)):
            parent, child = self.grants[i - 1], self.grants[i]
            if child.delegator_id != parent.subject.subject_id:
                raise InvalidDelegation(f"hop {i}: delegator mismatch")
            validate_delegation(parent, child)

    def root_effective_subset(self) -> bool:
        """Every child ⊆ parent along chain."""
        for i in range(1, len(self.grants)):
            if not authority_subset(self.grants[i], self.grants[i - 1]):
                return False
        return True
