# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from responsibleai.global_directory.person.signals import ScoredPersonCandidate


@dataclass
class RefinementSession:
    session_id: str
    query: str
    candidate_keys: list[str] = field(default_factory=list)
    catalog_entries: dict[str, dict] = field(default_factory=dict)
    scored: list[ScoredPersonCandidate] = field(default_factory=list)
    discovery_completed: bool = False


class RefinementStore:
    def __init__(self) -> None:
        self._sessions: dict[str, RefinementSession] = {}

    def create(self, query: str) -> RefinementSession:
        session_id = f"ref_{uuid.uuid4().hex[:16]}"
        session = RefinementSession(session_id=session_id, query=query)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> RefinementSession | None:
        return self._sessions.get(session_id)
