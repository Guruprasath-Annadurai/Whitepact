# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for the `whitepact` compatibility alias package.

MIGRATION_WHITEPACT_V2.md Section 3: `import whitepact` must re-export
the exact same objects as `import responsibleai` — identity, not just
equal-looking copies — so existing `responsibleai` users and new
`whitepact` users share one implementation, not two that could drift
apart.
"""

from __future__ import annotations

import responsibleai
import whitepact


class TestPublicApiIdentity:
    """Every name in whitepact.__all__ must be the identical object as
    the one responsibleai exports — not a re-imported copy, which would
    defeat isinstance() checks and shared module-level state."""

    def test_all_matches_responsibleai(self) -> None:
        assert whitepact.__all__ == responsibleai.__all__

    def test_every_exported_name_is_the_same_object(self) -> None:
        assert whitepact.__all__, "responsibleai.__all__ should not be empty"
        for name in whitepact.__all__:
            whitepact_obj = getattr(whitepact, name)
            responsibleai_obj = getattr(responsibleai, name)
            assert whitepact_obj is responsibleai_obj, (
                f"whitepact.{name} is not identical to responsibleai.{name}"
            )

    def test_version_matches(self) -> None:
        assert whitepact.__version__ == responsibleai.__version__

    def test_version_matches_package_metadata(self) -> None:
        # Catches exactly the drift this alias package's first commit
        # found and fixed: responsibleai.__version__ was hardcoded to
        # "0.4.0" while pyproject.toml (and the running app) had long
        # since moved to 1.2.0.
        import tomllib
        from pathlib import Path

        pyproject = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())
        assert whitepact.__version__ == pyproject["project"]["version"]


class TestFunctionalEquivalence:
    """Not just importable -- actually usable, producing identical
    results to the responsibleai-imported classes."""

    def test_trust_score_engine_works_via_whitepact_import(self) -> None:
        engine = whitepact.TrustScoreEngine()
        score = engine.compute(
            fairness=0.9,
            privacy=0.9,
            security=0.9,
            robustness=0.9,
            compliance=0.9,
            authenticity=0.9,
        )
        assert score.overall == 90.0
        assert score.grade == "A"

    def test_guardrails_engine_works_via_whitepact_import(self) -> None:
        guardrails = whitepact.GuardrailsEngine()
        result = guardrails.scan("My email is test@example.com")
        assert result.is_blocked is True

    def test_isinstance_checks_work_across_import_paths(self) -> None:
        # A caller mixing `whitepact.TrustScoreEngine()` construction with
        # `isinstance(x, responsibleai.TrustScoreEngine)` (or vice versa,
        # e.g. a library built against one import path checked by
        # application code built against the other) must not break --
        # this only holds if the two names are the same class object.
        instance = whitepact.TrustScoreEngine()
        assert isinstance(instance, responsibleai.TrustScoreEngine)


class TestPackageMetadata:
    def test_whitepact_is_registered_in_wheel_packages(self) -> None:
        import tomllib
        from pathlib import Path

        pyproject = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())
        packages = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
        assert "src/whitepact" in packages
