#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Byte-compatible Didit V2 canonical JSON + HMAC cross-check.

Mirrors WhitePact frozen #244 tip:
  src/responsibleai/enterprise/didit.py :: canonical / _normalize
without importing the full package (main lacks Didit module).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import sys


def _normalize(value):
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite JSON")
        return int(value) if value.is_integer() else value
    return value


def canonical(value) -> bytes:
    return json.dumps(
        _normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "--digest":
        data = json.loads(argv[1])
        print(hashlib.sha256(canonical(data)).hexdigest())
        return 0
    if len(argv) >= 3 and argv[0] == "--hmac":
        secret = argv[1].encode("utf-8")
        data = json.loads(argv[2])
        print(hmac.new(secret, canonical(data), hashlib.sha256).hexdigest())
        return 0
    if len(argv) >= 2 and argv[0] == "--canonical":
        data = json.loads(argv[1])
        sys.stdout.buffer.write(canonical(data))
        return 0
    print(
        "usage: python_canonical_crosscheck.py --digest JSON | --hmac SECRET JSON | --canonical JSON",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
