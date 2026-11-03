"""Configuration, release exporter, and boundary regression tests."""

from __future__ import annotations

import json
import runpy
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from whitepact_community.config import load_config
from whitepact_community.errors import ConfigurationError
from whitepact_community.release_control import (
    DefaultDenyExporter,
    ExportAuthorization,
    ExportDenied,
    ReplayLedger,
    TrustRoot,
    compute_tree_digest,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_malformed_config(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(bad)


def test_forbidden_secret_keys_rejected(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.json"
    # Value is intentionally non-secret; rejection is keyed on forbidden key names.
    cfg.write_text(json.dumps({"org_id": "x", "stripe_secret_key": "REDACTED"}), encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(cfg)


def test_valid_config(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"org_id": "demo", "log_level": "info"}), encoding="utf-8")
    loaded = load_config(cfg)
    assert loaded.org_id == "demo"
    assert loaded.log_level == "INFO"


def test_default_deny_exporter_empty_allowlist(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello", encoding="utf-8")
    digest = compute_tree_digest(src)
    replay = ReplayLedger(path=tmp_path / "replay.log")
    exporter = DefaultDenyExporter(
        approved_public_allowlist=frozenset(),
        trust_roots=[TrustRoot(root_id="synthetic", public_key_pem="TEST")],
        replay=replay,
    )
    auth = ExportAuthorization(
        authorization_id="auth-1",
        source_tree_sha256=digest,
        reviewer_id="antigravity",
        ci_provenance_id="local-ci-1",
        approved_paths=frozenset(),
        nonce="n1",
    )
    with pytest.raises(ExportDenied, match="Default-deny"):
        exporter.export(auth, source_root=src, destination=tmp_path / "out")


def test_exporter_replay_and_tree_binding(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello", encoding="utf-8")
    digest = compute_tree_digest(src)
    replay = ReplayLedger(path=tmp_path / "replay.log")
    exporter = DefaultDenyExporter(
        trust_roots=[TrustRoot(root_id="synthetic", public_key_pem="TEST")],
        replay=replay,
    )
    auth = ExportAuthorization(
        authorization_id="auth-2",
        source_tree_sha256=digest,
        reviewer_id="antigravity",
        ci_provenance_id="local-ci-2",
        approved_paths=frozenset(),
        nonce="n2",
    )
    exporter.verify_authorization(auth, source_root=src)
    with pytest.raises(ExportDenied, match="Replay"):
        exporter.verify_authorization(auth, source_root=src)

    bad = ExportAuthorization(
        authorization_id="auth-3",
        source_tree_sha256="0" * 64,
        reviewer_id="antigravity",
        ci_provenance_id="local-ci-3",
        nonce="n3",
    )
    with pytest.raises(ExportDenied, match="digest mismatch"):
        exporter.verify_authorization(bad, source_root=src)


def test_exporter_expired(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello", encoding="utf-8")
    exporter = DefaultDenyExporter(
        trust_roots=[TrustRoot(root_id="synthetic", public_key_pem="TEST")],
    )
    auth = ExportAuthorization(
        authorization_id="auth-4",
        source_tree_sha256=compute_tree_digest(src),
        reviewer_id="antigravity",
        ci_provenance_id="local-ci-4",
        nonce="n4",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(ExportDenied, match="expired"):
        exporter.verify_authorization(auth, source_root=src)


def test_static_boundary_script_on_source() -> None:
    script = PACKAGE_ROOT / "scripts" / "verify_package_boundary.py"
    argv = sys.argv
    try:
        sys.argv = [
            str(script),
            "--package-src",
            str(PACKAGE_ROOT / "src" / "whitepact_community"),
        ]
        ns = runpy.run_path(str(script), run_name="__not_main__")
        assert ns["main"]() == 0
    finally:
        sys.argv = argv
