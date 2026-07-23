"""Tests for scripts/generate_compliance_kit.py — the scaffolding tool
behind the compliance-starter-kit product (STRATEGY_ROADMAP.md Part 0,
Item 4)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "generate_compliance_kit.py"
_spec = importlib.util.spec_from_file_location("generate_compliance_kit", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
sys.modules["generate_compliance_kit"] = _module
_spec.loader.exec_module(_module)


class TestSlugify:
    def test_basic_name(self):
        assert _module._slugify("Acme Corp") == "acme-corp"

    def test_special_characters_stripped(self):
        assert _module._slugify("Acme, Inc.!") == "acme-inc"

    def test_empty_falls_back(self):
        assert _module._slugify("") == "company"


class TestGenerate:
    def test_writes_both_templates(self, tmp_path):
        target = _module.generate("Acme Corp", output_dir=tmp_path / "out")
        assert (target / "CAIQ_TEMPLATE.md").exists()
        assert (target / "NIST_CSF_TEMPLATE.md").exists()

    def test_substitutes_company_name(self, tmp_path):
        target = _module.generate("Acme Corp", output_dir=tmp_path / "out")
        content = (target / "CAIQ_TEMPLATE.md").read_text()
        assert "Acme Corp" in content
        assert "{{COMPANY_NAME}}" not in content

    def test_substitutes_date(self, tmp_path):
        target = _module.generate("Acme Corp", output_dir=tmp_path / "out")
        content = (target / "NIST_CSF_TEMPLATE.md").read_text()
        assert "{{DATE}}" not in content

    def test_default_output_dir_uses_slug(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        target = _module.generate("Weird & Co.")
        assert target.name == "weird-co-compliance-kit"
        assert target.exists()

    def test_missing_template_dir_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_module, "_TEMPLATE_DIR", tmp_path / "does-not-exist")
        with pytest.raises(FileNotFoundError):
            _module.generate("Acme", output_dir=tmp_path / "out")
