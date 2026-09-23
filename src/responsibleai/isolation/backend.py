# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Abstract protocol for runtime isolation backends."""

from __future__ import annotations

from typing import Protocol

from responsibleai.isolation.models import ExecutionOutcome, IsolatedExecutionRequest


class IsolationBackend(Protocol):
    """Execution backend interface for isolated task evaluation."""

    async def execute(self, request: IsolatedExecutionRequest) -> ExecutionOutcome:
        """Execute a narrow task in isolation and return a sanitized outcome."""
        ...

    def is_available(self) -> bool:
        """Check if the backend runtime is functional and ready."""
        ...
