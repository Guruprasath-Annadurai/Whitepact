# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CapabilityKind(StrEnum):
    DIRECT_TOOL = "DIRECT_TOOL"
    RESOURCE = "RESOURCE"
    CREDENTIAL_DERIVED = "CREDENTIAL_DERIVED"
    INFORMATION_DERIVED = "INFORMATION_DERIVED"
    COMPOSED = "COMPOSED"


@dataclass(frozen=True, slots=True)
class CapabilityRef:
    tenant_id: str
    subject_id: str
    capability_id: str
    kind: CapabilityKind
    """Capability is reachability only — never implies authority."""
