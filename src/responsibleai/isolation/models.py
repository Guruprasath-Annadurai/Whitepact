# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Data models for WhitePact Independent Runtime Isolation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class BackendMode(StrEnum):
    """Runtime isolation backend execution modes."""

    DOCKER = "docker"
    LOCAL_DEV = "local_dev"


class NetworkPolicy(StrEnum):
    """Network containment policies for isolated execution."""

    NONE = "none"
    ALLOWLISTED_EGRESS = "allowlisted_egress"


@dataclass(frozen=True)
class ResourceLimits:
    """Resource constraints enforced on isolated executions."""

    max_memory_mb: int = 256
    cpu_cores: float = 0.5
    max_pids: int = 32
    max_file_descriptors: int = 128
    wall_timeout_seconds: float = 15.0
    max_output_bytes: int = 65536  # 64 KB limit for stdout/stderr/payload


@dataclass(frozen=True)
class IsolationProfile:
    """High-level security profile binding resources and policies."""

    name: str = "STRICT"
    network_policy: NetworkPolicy = NetworkPolicy.NONE
    resources: ResourceLimits = field(default_factory=ResourceLimits)
    read_only_root: bool = True
    drop_all_capabilities: bool = True
    no_new_privileges: bool = True
    allow_environment_passthrough: bool = False


DEFAULT_STRICT_PROFILE = IsolationProfile()

DEFAULT_COMPLIANCE_PROFILE = IsolationProfile(
    name="COMPLIANCE_EVAL",
    network_policy=NetworkPolicy.NONE,
    resources=ResourceLimits(
        max_memory_mb=512,
        cpu_cores=1.0,
        max_pids=64,
        wall_timeout_seconds=30.0,
    ),
)


@dataclass(frozen=True)
class IsolatedExecutionRequest:
    """The narrow execution request passed to the independent execution plane."""

    action_id: str
    organization_id: str
    action_type: str
    arguments: dict[str, Any]
    profile: IsolationProfile = field(default_factory=IsolationProfile)
    environment_overrides: dict[str, str] = field(default_factory=dict)
    workspace_files: dict[str, str | bytes] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionOutcome:
    """Sanitized result returned from the isolated execution plane."""

    action_id: str
    exit_code: int
    result_payload: Any
    stdout: str
    stderr: str
    duration_seconds: float
    memory_peak_mb: float = 0.0
    timed_out: bool = False
    violation: str | None = None

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and self.violation is None
