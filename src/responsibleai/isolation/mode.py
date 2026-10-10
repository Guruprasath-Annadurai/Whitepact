# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The one place that decides whether tool execution may run without isolation.

Isolation is the default. Execution outside an isolation backend (same process, or the
local subprocess backend that provides no network or filesystem containment) is allowed
only when BOTH hold:

* ``ENVIRONMENT`` is not ``production``, and
* ``WHITEPACT_ALLOW_UNISOLATED_EXECUTION`` is exactly ``1``.

Earlier revisions inverted this: isolation was engaged only if ``ENVIRONMENT=production``
or ``WHITEPACT_ISOLATION_BACKEND`` was set, so a deployment that simply forgot those
variables ran every governed tool in-process with the host's full network and filesystem,
bypassing both Phase 2 isolation and controlled egress. A security boundary must not
depend on an operator remembering to switch it on.
"""

from __future__ import annotations

import os

UNISOLATED_EXECUTION_ENV = "WHITEPACT_ALLOW_UNISOLATED_EXECUTION"
SYNTHETIC_HOST_TOOL_ENV = "WHITEPACT_ALLOW_SYNTHETIC_HOST_TOOL"


def is_production() -> bool:
    return os.environ.get("ENVIRONMENT", "").strip().lower() == "production"


def unisolated_execution_allowed() -> bool:
    """True only for an explicit, non-production, local-development opt-in."""
    if is_production():
        return False
    return os.environ.get(UNISOLATED_EXECUTION_ENV) == "1"


_PRODUCTION_NAMES = {"production", "prod"}


def synthetic_host_tool_allowed() -> bool:
    """True only for the test-only database fixture, in an explicit non-production setup.

    ``test.counter.increment`` writes to the server process's own database engine. A
    container started with ``--network=none`` and no credentials cannot do that, by design,
    so this one fixture may run host-side. It is not a general escape hatch: real tools
    still require isolation, the fixture refuses production itself, and every environment
    variable that names the deployment must be non-production as well as this switch set.
    """
    for name in ("ENVIRONMENT", "WHITEPACT_ENV", "RAI_ENVIRONMENT"):
        if os.environ.get(name, "").strip().lower() in _PRODUCTION_NAMES:
            return False
    return os.environ.get(SYNTHETIC_HOST_TOOL_ENV) == "1"
