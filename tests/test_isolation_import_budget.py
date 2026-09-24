# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Prove isolated children can import dispatch under the STRICT 256 MiB ceiling.

HallucinationDetector pulls sklearn/scipy. That import is required only for
``rai_hallucination``, not for the isolation runner path (e.g. rai_trust_score).
Raising RLIMIT_AS would weaken the sandbox; the product fix is lazy loading.

Darwin (macOS) does not support ``RLIMIT_AS``. This test remains
platform-aware: the STRICT 256 MiB production ceiling is unchanged on Linux.
On Darwin we still prove lazy import of sklearn/scipy/numpy, and we do not
treat the missing primitive as a product failure.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

from responsibleai.isolation.models import DEFAULT_STRICT_PROFILE


def test_dispatch_import_under_strict_as_limit_does_not_load_sklearn() -> None:
    mem_bytes = DEFAULT_STRICT_PROFILE.resources.max_memory_mb * 1024 * 1024
    assert mem_bytes == 256 * 1024 * 1024
    script = textwrap.dedent(
        """
        import resource
        import sys
        mem = int(sys.argv[1])
        darwin = sys.platform == "darwin"
        as_supported = hasattr(resource, "RLIMIT_AS") and not darwin
        if as_supported:
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        from responsibleai.mcp.tools import dispatch_tool
        assert callable(dispatch_tool)
        assert "sklearn" not in sys.modules
        assert "scipy" not in sys.modules
        assert "numpy" not in sys.modules
        if not as_supported:
            sys.stderr.write("RLIMIT_AS unsupported on this platform; lazy-import still verified\\n")
        """
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    env["OPENBLAS_NUM_THREADS"] = "1"
    proc = subprocess.run(
        [sys.executable, "-c", script, str(mem_bytes)],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_strict_profile_memory_ceiling_is_256_mib() -> None:
    """Production runtime retains the Linux STRICT 256 MiB ceiling."""
    assert DEFAULT_STRICT_PROFILE.resources.max_memory_mb == 256
