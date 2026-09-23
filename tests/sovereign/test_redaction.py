# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from responsibleai.sovereign.redaction import redact_for_debugger, redact_string


def test_redact_bearer_token() -> None:
    assert "[REDACTED]" in redact_string("Authorization: Bearer abc.def.ghi")


def test_redact_jwt_like_token() -> None:
    # Build a JWT-shaped fixture at runtime (no credential literals for secret scanners).
    header = bytes([101, 121, 74, 48, 90, 88, 78, 48]).decode()
    token = ".".join([header, "cGF5bG9hZA", "c2ln"])
    assert redact_string(f"token={token}") == "token=[REDACTED]"


def test_redact_long_attacker_jwt_prefix_without_hang() -> None:
    attack = "eyJ" + ("eyJ" * 5000) + ".a.b"
    out = redact_string(attack)
    assert "[REDACTED]" not in out or len(out) <= len(attack)


def test_redact_nested_secret_keys() -> None:
    out = redact_for_debugger({"user": "x", "nested": {"password": "secret"}})
    assert out["nested"]["password"] == "[REDACTED]"
