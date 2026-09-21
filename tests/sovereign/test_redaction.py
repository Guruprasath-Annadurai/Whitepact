# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from responsibleai.sovereign.redaction import redact_for_debugger, redact_string


def test_redact_bearer_token() -> None:
    assert "[REDACTED]" in redact_string("Authorization: Bearer abc.def.ghi")


def test_redact_nested_secret_keys() -> None:
    out = redact_for_debugger({"user": "x", "nested": {"password": "secret"}})
    assert out["nested"]["password"] == "[REDACTED]"
