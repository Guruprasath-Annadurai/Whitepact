# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""P1-04 — sandbox Paddle regression matrix entry point (delegates to canonical suites)."""

from __future__ import annotations

from pathlib import Path


def test_paddle_sandbox_canonical_tests_present() -> None:
    root = Path(__file__).resolve().parent
    expected = [
        "test_auth_canonical_seams.py",
        "test_web_paddle_billing_routes.py",
        "test_paddle_billing_service.py",
    ]
    for name in expected:
        assert (root / name).is_file(), f"missing Paddle sandbox suite: {name}"
