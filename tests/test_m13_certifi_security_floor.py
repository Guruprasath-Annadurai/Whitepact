"""Prevent package and tooling locks from restoring a distrusted CA bundle."""

import re
import ssl
import tomllib
from importlib.metadata import version
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
FIXED = Version("2026.10.19")


def test_distributions_require_corrected_ca_bundle():
    for relative in ("pyproject.toml", "sdk/python/pyproject.toml"):
        manifest = tomllib.loads((ROOT / relative).read_text())
        requirements = [Requirement(value) for value in manifest["project"]["dependencies"]]
        certifi = next(item for item in requirements if item.name == "certifi")
        assert FIXED in certifi.specifier
        assert Version("2026.7.22") not in certifi.specifier
        assert Version("2026.10.18") not in certifi.specifier


def test_runtime_and_security_locks_cannot_downgrade_ca_bundle():
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    certifi = next(item for item in lock["package"] if item["name"] == "certifi")
    assert Version(certifi["version"]) >= FIXED
    security = (ROOT / "requirements-security.lock").read_text()
    match = re.search(r"(?m)^certifi==([^\s]+)", security)
    assert match is not None
    assert Version(match.group(1)) >= FIXED
    assert "certifi>=2026.10.19" in (ROOT / "requirements-security.in").read_text()


def test_default_httpcore_context_loads_corrected_bundle(monkeypatch):
    import certifi
    import httpcore

    assert Version(version("certifi")) >= FIXED
    bundle = certifi.where()
    calls = []

    def locate_bundle():
        calls.append(bundle)
        return bundle

    monkeypatch.setattr(certifi, "where", locate_bundle)
    context = httpcore.default_ssl_context()
    assert calls == [bundle]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.cert_store_stats()["x509_ca"] > 0
