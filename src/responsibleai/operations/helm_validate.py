# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Validate Helm values files against Launch Cell B deployment contracts.

Usage:
    python -m responsibleai.operations.helm_validate path/to/values.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from responsibleai.operations.helm_contract import collect_helm_profile_errors


def load_values(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("values file must be a mapping")
    return data


def validate_file(path: Path) -> list[str]:
    return collect_helm_profile_errors(load_values(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WhitePact Helm values validator")
    parser.add_argument("values", type=Path, help="Helm values YAML file")
    args = parser.parse_args(argv)
    try:
        errors = validate_file(args.values)
    except Exception as exc:
        print(f"HELM_VALUES_INVALID: {exc}", file=sys.stderr)
        return 1
    if errors:
        for err in errors:
            print(f"HELM_VALUES_INVALID: {err}", file=sys.stderr)
        return 1
    print("HELM_VALUES_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
