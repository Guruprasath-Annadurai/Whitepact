# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Evaluation package exports.

Names are resolved lazily so isolated execution children can import
``responsibleai.eval.benchmarks`` without pulling sklearn/numpy via
``ModelComparator`` / ``HallucinationDetector``.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "BenchmarkResult",
    "BenchmarkRunner",
    "BenchmarkSuite",
    "ComparisonResult",
    "DatasetBiasScanner",
    "DatasetScanResult",
    "EvalPrompt",
    "ModelComparator",
    "ModelResponse",
    "RegressionAlert",
    "RegressionDetector",
    "RegressionSeverity",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "BenchmarkResult": ("responsibleai.eval.models", "BenchmarkResult"),
    "BenchmarkRunner": ("responsibleai.eval.benchmarks", "BenchmarkRunner"),
    "BenchmarkSuite": ("responsibleai.eval.models", "BenchmarkSuite"),
    "ComparisonResult": ("responsibleai.eval.models", "ComparisonResult"),
    "DatasetBiasScanner": ("responsibleai.eval.dataset_scanner", "DatasetBiasScanner"),
    "DatasetScanResult": ("responsibleai.eval.models", "DatasetScanResult"),
    "EvalPrompt": ("responsibleai.eval.models", "EvalPrompt"),
    "ModelComparator": ("responsibleai.eval.comparator", "ModelComparator"),
    "ModelResponse": ("responsibleai.eval.models", "ModelResponse"),
    "RegressionAlert": ("responsibleai.eval.models", "RegressionAlert"),
    "RegressionDetector": ("responsibleai.eval.regression", "RegressionDetector"),
    "RegressionSeverity": ("responsibleai.eval.models", "RegressionSeverity"),
}


def __getattr__(name: str) -> Any:
    spec = _EXPORTS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(spec[0])
    value = getattr(module, spec[1])
    globals()[name] = value
    return value
