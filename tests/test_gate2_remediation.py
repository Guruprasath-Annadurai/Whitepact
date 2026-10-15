# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Gate 2 remediation: restore safety, encryption, HSTS, proxy identity, origin auth."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from responsibleai.dashboard.edge_policy import hsts_header_value, preload_suppressed, robots_tag
from responsibleai.ops.backup_crypto import (
    BackupRejectedError,
    assert_upload_allowed,
    decrypt_dump,
    encrypt_dump,
    seal_compressed,
)
from responsibleai.ops.client_ip import resolve_client_ip
from responsibleai.ops.gate2_signals import SignalSnapshot, evaluate
from responsibleai.ops.r2_retention import BackupObject, plan_retention
from responsibleai.ops.restore_flow import cutover_sql
from tests.gate2_bash32 import (
    Bash32RejectedError,
    Bash32UnavailableError,
    bash_version,
    discover_bash32,
)

ROOT = Path(__file__).resolve().parents[1]
RESTORE = ROOT / "scripts" / "restore-postgres.sh"
BACKUP = ROOT / "scripts" / "backup-postgres.sh"
UPLOAD = ROOT / "scripts" / "cloud" / "upload-backup-to-r2.sh"
DUMP = b"--\n-- PostgreSQL database dump\n--\nSELECT 1;\n"
PG_ENV = {
    "PGHOST": "127.0.0.1",
    "PGPORT": "55432",
    "PGUSER": "wp",
    "PGPASSWORD": "wp",
}


def _env(**extra: str) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["WHITEPACT_PYTHON"] = sys.executable
    env.update(extra)
    return env


def _key() -> str:
    return Fernet.generate_key().decode("ascii")


def _artifact(
    tmp_path: Path,
    plain: bytes = DUMP,
    secret: str | None = None,
    *,
    relations: list[str] | None = None,
) -> Path:
    secret = secret or _key()
    dest = tmp_path / "backup.sql.gz.enc"
    encrypt_dump(
        plain,
        secret,
        dest,
        database="fixture",
        tool_version="1.3.1",
        required_relations=relations,
    )
    return dest


def _psql(*args: str, db: str = "postgres") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["psql", "-d", db, "-v", "ON_ERROR_STOP=1", "-X", "-q", *args],
        check=False,
        capture_output=True,
        text=True,
        env=_env(**PG_ENV),
    )


def _postgres_up() -> bool:
    result = _psql("-tAc", "SELECT 1")
    return result.returncode == 0 and result.stdout.strip() == "1"


def _restore_databases() -> set[str]:
    result = _psql("-tAc", "SELECT datname FROM pg_database WHERE datname LIKE 'wp_restore_%';")
    assert result.returncode == 0, result.stderr
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def test_restore_script_does_not_drop_the_active_database_first() -> None:
    text = RESTORE.read_text(encoding="utf-8")
    assert "DROP DATABASE IF EXISTS ${DB}" not in text
    assert 'DROP DATABASE IF EXISTS "$DB"' not in text
    assert "DROP DATABASE IF EXISTS ${ACTIVE_DB}" not in text
    assert text.index("prepare-restore") < text.index("CREATE DATABASE")
    assert text.index("CREATE DATABASE") < text.index("DROP DATABASE IF EXISTS")
    first, second = cutover_sql("responsibleai", "wp_restore_abc", "responsibleai_prev_abc")
    assert "DROP" not in first
    assert "DROP" not in second
    assert "RENAME TO" in first and "RENAME TO" in second
    assert "mapfile" not in text
    assert "readarray" not in text


def test_corrupt_wrong_checksum_wrong_key_empty_truncated_and_missing_manifest(
    tmp_path: Path,
) -> None:
    secret = _key()
    dest = _artifact(tmp_path, secret=secret)
    calls = tmp_path / "psql.log"
    spy = tmp_path / "psql"
    spy.write_text('#!/bin/sh\necho "$0 $*" >> "$PSQL_LOG"\nexit 0\n', encoding="utf-8")
    spy.chmod(0o755)
    env = _env(
        PATH=f"{tmp_path}:{os.environ.get('PATH', '')}",
        PSQL_LOG=str(calls),
        WHITEPACT_BACKUP_ENCRYPTION_KEY=secret,
        WHITEPACT_RESTORE_LOCAL="1",
        PGUSER="wp",
        PGDATABASE="responsibleai",
    )

    def run(path: Path, key: str | None = None) -> subprocess.CompletedProcess[str]:
        run_env = dict(env)
        if key is not None:
            run_env["WHITEPACT_BACKUP_ENCRYPTION_KEY"] = key
        return subprocess.run(
            ["bash", str(RESTORE), str(path)],
            check=False,
            capture_output=True,
            text=True,
            env=run_env,
        )

    missing = run(tmp_path / "nope.sql.gz.enc")
    assert missing.returncode != 0

    empty = tmp_path / "empty.sql.gz.enc"
    empty.write_bytes(b"")
    assert run(empty).returncode != 0

    no_manifest = tmp_path / "bare.sql.gz.enc"
    no_manifest.write_bytes(dest.read_bytes())
    assert run(no_manifest).returncode != 0

    flipped = tmp_path / "bad-sum.sql.gz.enc"
    flipped.write_bytes(dest.read_bytes())
    manifest = json.loads(dest.with_name(dest.name + ".manifest.json").read_text(encoding="utf-8"))
    manifest["ciphertext_sha256"] = "0" * 64
    flipped.with_name(flipped.name + ".manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    wrong_sum = run(flipped)
    assert wrong_sum.returncode != 0
    assert "checksum" in wrong_sum.stderr.lower()

    wrong_key = run(dest, key=_key())
    assert wrong_key.returncode != 0
    assert "decryption" in wrong_key.stderr.lower() or "key" in wrong_key.stderr.lower()

    truncated = tmp_path / "trunc.sql.gz.enc"
    gzip_member = b"\x1f\x8btruncated"
    seal_compressed(
        gzip_member,
        DUMP,
        secret,
        truncated,
        database="fixture",
        tool_version="1.3.1",
    )
    truncated_result = run(truncated)
    assert truncated_result.returncode != 0
    assert calls.exists() is False


def test_invalid_sql_restore_leaves_source_and_drops_only_staging(tmp_path: Path) -> None:
    if not _postgres_up():
        pytest.fail("isolated Postgres is not listening on 127.0.0.1:55432")
    suffix = os.urandom(3).hex()
    source = f"wp_src_{suffix}"
    assert _psql("-c", f'CREATE DATABASE "{source}"').returncode == 0
    before = _restore_databases()
    try:
        created = _psql(
            "-c",
            "CREATE TABLE gate2_marker (id int primary key); INSERT INTO gate2_marker VALUES (7);",
            db=source,
        )
        assert created.returncode == 0, created.stderr
        secret = _key()
        bad = tmp_path / "bad.sql.gz.enc"
        encrypt_dump(
            b"--\n-- PostgreSQL database dump\n--\nNOT VALID SQL;\n",
            secret,
            bad,
            database=source,
            tool_version="1.3.1",
        )
        result = subprocess.run(
            ["bash", str(RESTORE), str(bad)],
            check=False,
            capture_output=True,
            text=True,
            env=_env(
                **PG_ENV,
                WHITEPACT_BACKUP_ENCRYPTION_KEY=secret,
                WHITEPACT_RESTORE_LOCAL="1",
                PGDATABASE=source,
            ),
        )
        assert result.returncode != 0, result.stdout + result.stderr
        still = _psql("-tAc", "SELECT id FROM gate2_marker;", db=source)
        assert still.stdout.strip() == "7"
        assert _restore_databases() == before
    finally:
        for name in _restore_databases() - before:
            _psql("-c", f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE);')
        _psql("-c", f'DROP DATABASE IF EXISTS "{source}" WITH (FORCE);')


def test_backup_restore_drill_keeps_source_until_copy_verifies(tmp_path: Path) -> None:
    if not _postgres_up():
        pytest.fail("isolated Postgres is not listening on 127.0.0.1:55432")
    suffix = os.urandom(3).hex()
    source = f"wp_src_{suffix}"
    secret = _key()
    assert _psql("-c", f'CREATE DATABASE "{source}"').returncode == 0
    staging_name = ""
    before = _restore_databases()
    try:
        created = _psql(
            "-c",
            "CREATE TABLE gate2_marker (id int primary key, note text); INSERT INTO gate2_marker VALUES (7, 'kept');",
            db=source,
        )
        assert created.returncode == 0, created.stderr
        backup = subprocess.run(
            ["bash", str(BACKUP), str(tmp_path)],
            check=False,
            capture_output=True,
            text=True,
            env=_env(
                **PG_ENV,
                PGDATABASE=source,
                WHITEPACT_BACKUP_LOCAL="1",
                WHITEPACT_BACKUP_ENCRYPTION_KEY=secret,
                WHITEPACT_BACKUP_REQUIRED_RELATIONS="gate2_marker",
            ),
        )
        assert backup.returncode == 0, backup.stderr
        artifacts = list(tmp_path.glob("*.sql.gz.enc"))
        assert len(artifacts) == 1
        assert not list(tmp_path.glob("*.sql.gz"))
        assert not list(tmp_path.glob("*.sql"))
        changed = _psql("-c", "INSERT INTO gate2_marker VALUES (8, 'after-backup');", db=source)
        assert changed.returncode == 0, changed.stderr
        restored = subprocess.run(
            ["bash", str(RESTORE), str(artifacts[0])],
            check=False,
            capture_output=True,
            text=True,
            env=_env(
                **PG_ENV,
                PGDATABASE=source,
                WHITEPACT_BACKUP_ENCRYPTION_KEY=secret,
                WHITEPACT_RESTORE_LOCAL="1",
            ),
        )
        assert restored.returncode == 0, restored.stdout + restored.stderr
        assert "was not dropped" in restored.stdout
        for line in restored.stdout.splitlines():
            marker = "Staging restore verified:"
            if marker in line:
                staging_name = line.split(marker, 1)[1].strip()
        assert staging_name.startswith("wp_restore_")
        copy = _psql("-tAc", "SELECT id || note FROM gate2_marker ORDER BY id;", db=staging_name)
        assert copy.stdout.strip() == "7kept"
        source_rows = _psql("-tAc", "SELECT count(*) FROM gate2_marker;", db=source)
        assert source_rows.stdout.strip() == "2"
    finally:
        for name in {staging_name} | (_restore_databases() - before):
            if name:
                _psql("-c", f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE);')
        _psql("-c", f'DROP DATABASE IF EXISTS "{source}" WITH (FORCE);')


def test_upload_refuses_plaintext_and_accepts_ciphertext(tmp_path: Path) -> None:
    secret = _key()
    dest = _artifact(tmp_path, secret=secret)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "aws.log"
    aws = bin_dir / "aws"
    aws.write_text(
        '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$AWS_LOG"\nexit 0\n',
        encoding="utf-8",
    )
    aws.chmod(0o755)
    plain = tmp_path / "plain.sql.gz"
    plain.write_bytes(b"plaintext")
    env = _env(
        PATH=f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        AWS_LOG=str(log),
        R2_ACCESS_KEY_ID="test",
        R2_SECRET_ACCESS_KEY="test",
        R2_BUCKET="bucket",
        R2_ENDPOINT="https://example.invalid",
    )
    refused = subprocess.run(
        ["bash", str(UPLOAD), str(plain)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert refused.returncode != 0
    assert not log.exists()
    with pytest.raises(BackupRejectedError):
        assert_upload_allowed(plain)
    accepted = subprocess.run(
        ["bash", str(UPLOAD), str(dest)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert accepted.returncode == 0, accepted.stderr
    uploaded = log.read_text(encoding="utf-8")
    assert dest.name in uploaded
    assert ".sql.gz " not in uploaded
    assert "manifest.json" in uploaded


@pytest.mark.parametrize(
    ("stage", "include", "expected"),
    [
        ("disabled", None, None),
        ("initial", False, "max-age=0"),
        ("stage1", False, "max-age=300"),
        ("stage2", None, "max-age=86400; includeSubDomains"),
    ],
)
def test_hsts_stages(stage: str, include: bool | None, expected: str | None) -> None:
    header = hsts_header_value(
        environment="production",
        stage=stage,
        include_subdomains=include,
        preload=False,
        preload_authorized=False,
    )
    assert header == expected
    if header:
        assert "preload" not in header
        assert "31536000" not in header


def test_hsts_preload_requires_authorization_and_dev_is_not_year_long() -> None:
    suppressed = hsts_header_value(
        environment="production",
        stage="stage2",
        include_subdomains=True,
        preload=True,
        preload_authorized=False,
    )
    assert suppressed == "max-age=86400; includeSubDomains"
    assert preload_suppressed(preload=True, preload_authorized=False)
    authorized = hsts_header_value(
        environment="production",
        stage="stage2",
        include_subdomains=True,
        preload=True,
        preload_authorized=True,
    )
    assert authorized is not None and authorized.endswith("preload")
    assert (
        hsts_header_value(
            environment="development",
            stage=None,
            include_subdomains=None,
            preload=False,
            preload_authorized=False,
        )
        is None
    )
    production_default = hsts_header_value(
        environment="production",
        stage=None,
        include_subdomains=None,
        preload=False,
        preload_authorized=False,
    )
    assert production_default == "max-age=300"


def test_staging_noindex_is_separate_from_production() -> None:
    assert robots_tag(environment="staging", robots_noindex=None) == "noindex, nofollow"
    assert robots_tag(environment="production", robots_noindex=None) is None
    assert robots_tag(environment="production", robots_noindex=True) == "noindex, nofollow"
    assert robots_tag(environment="staging", robots_noindex=False) is None


def test_forwarded_headers_are_ignored_unless_peer_is_trusted() -> None:
    headers = {
        "X-Forwarded-For": "198.51.100.9, 203.0.113.4",
        "X-Real-IP": "198.51.100.8",
        "Forwarded": "for=198.51.100.7",
        "CF-Connecting-IP": "198.51.100.6",
    }
    assert (
        resolve_client_ip(peer="203.0.113.50", headers=headers, legacy_trust_forwarded=True)
        == "203.0.113.50"
    )
    assert (
        resolve_client_ip(
            peer="203.0.113.50",
            headers={"X-Forwarded-For": "010.000.000.001, 198.51.100.9"},
        )
        == "203.0.113.50"
    )
    trusted = resolve_client_ip(
        peer="10.0.0.8",
        headers=headers,
        trusted_proxy_cidrs=["10.0.0.0/8"],
    )
    assert trusted == "203.0.113.4"
    cloudflare = resolve_client_ip(
        peer="192.0.2.10",
        headers=headers,
        cloudflare_cidrs=["192.0.2.0/24"],
    )
    assert cloudflare == "198.51.100.6"
    untrusted_cf = resolve_client_ip(
        peer="203.0.113.50",
        headers={"CF-Connecting-IP": "198.51.100.6"},
        cloudflare_cidrs=["192.0.2.0/24"],
    )
    assert untrusted_cf == "203.0.113.50"
    mapped = resolve_client_ip(peer="::ffff:203.0.113.50", headers={})
    expanded = resolve_client_ip(peer="2001:db8:0:0:0:0:0:1", headers={})
    assert mapped == "203.0.113.50"
    assert expanded == "2001:db8::1"


def test_origin_contract_and_nginx_do_not_claim_lb_cidr_filter() -> None:
    contract = json.loads(
        (ROOT / "scripts/cloud/gate2/edge-contract.json").read_text(encoding="utf-8")
    )
    assert contract["origin_lockdown"]["lb_source_cidr_filter"] is False
    nginx = (ROOT / "deploy/origin/nginx-cloudflare-aop.conf").read_text(encoding="utf-8")
    assert "ssl_verify_client on;" in nginx
    assert "ssl_client_certificate" in nginx
    assert "proxy_pass http://127.0.0.1:8765;" in nginx
    assert "add_header Strict-Transport-Security" not in nginx
    terraform = (ROOT / "infra/terraform/modules/cloudflare-edge/gate2.tf").read_text(
        encoding="utf-8"
    )
    for needle in (
        "requests_per_period = 20",
        "requests_per_period = 10",
        "requests_per_period = 300",
        "requests_per_period = 120",
        "requests_per_period = 60",
        'action      = "log"',
        "plan_allows_waf_managed_rules",
        "plan_allows_rate_limit_rules",
    ):
        assert needle in terraform
    assert 'ssl              = "strict"' in terraform
    edge_main = (ROOT / "infra/terraform/modules/cloudflare-edge/main.tf").read_text(
        encoding="utf-8"
    )
    assert 'resource "cloudflare_zero_trust_tunnel_cloudflared" "admin"' in edge_main
    assert 'resource "cloudflare_tunnel" "admin"' not in edge_main
    assert "var.enable_waf_managed_rules && var.plan_allows_waf_managed_rules ? 1 : 0" in terraform


def test_backup_age_signal_is_defined_and_not_a_fake_alert() -> None:
    findings = evaluate(
        SignalSnapshot(
            backup_age_hours=30,
            backup_failed=False,
            restore_drill_failed=False,
            origin_tls_failed=False,
            disk_used_percent=10,
            db_connected=True,
            application_healthy=True,
            execution_healthy=True,
        )
    )
    age = next(item for item in findings if item["signal"] == "backup_age")
    assert age["condition_met"] is True
    assert age["alert_dispatched"] is False
    script = ROOT / "scripts/cloud/gate2/health_signals.sh"
    result = subprocess.run(
        ["bash", str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=_env(WHITEPACT_SIGNAL_BACKUP_AGE_HOURS="30"),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["alerts_dispatched"] is False
    assert any(
        item["signal"] == "backup_age" and item["condition_met"] for item in payload["signals"]
    )


def test_retention_timezone_boundary_and_dry_run_default(tmp_path: Path) -> None:
    now = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
    objects = [
        BackupObject("newest", now, True),
        BackupObject("fresh", now - timedelta(days=1), True),
        BackupObject("boundary", now - timedelta(days=30), True),
        BackupObject("stale", now - timedelta(days=31), True),
        BackupObject("la-boundary", datetime(2026, 2, 13, 16, 30, tzinfo=UTC), True),
    ]
    dry = plan_retention(objects, now=now, retain_days=30, min_recovery_points=2, tz_name="UTC")
    assert dry.dry_run is True
    assert "newest" not in dry.delete
    assert "fresh" not in dry.delete
    assert "boundary" not in dry.delete
    assert "stale" in dry.delete
    la = plan_retention(
        objects,
        now=now,
        retain_days=30,
        min_recovery_points=1,
        tz_name="America/Los_Angeles",
    )
    assert "newest" not in la.delete
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(
        json.dumps(
            {
                "now": now.isoformat(),
                "retain_days": 30,
                "min_recovery_points": 2,
                "tz": "UTC",
                "objects": [
                    {"key": item.key, "created_at": item.created_at.isoformat(), "viable": True}
                    for item in objects
                    if item.key != "la-boundary"
                ],
            }
        ),
        encoding="utf-8",
    )
    script = ROOT / "scripts/cloud/gate2/enforce_r2_retention.sh"
    dry_run = subprocess.run(
        ["bash", str(script), str(plan_file)],
        check=False,
        capture_output=True,
        text=True,
        env=_env(),
    )
    assert dry_run.returncode == 0, dry_run.stderr
    assert json.loads(dry_run.stdout)["dry_run"] is True
    deleted = subprocess.run(
        ["bash", str(script), "--delete", str(plan_file)],
        check=False,
        capture_output=True,
        text=True,
        env=_env(),
    )
    body = json.loads(deleted.stdout)
    assert body["dry_run"] is False
    assert "newest" not in body["delete"]
    assert "stale" in body["delete"]


def _manifest(path: Path) -> tuple[Path, dict[str, object]]:
    manifest_path = path.with_name(path.name + ".manifest.json")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("manifest must be an object")
    return manifest_path, {str(key): value for key, value in payload.items()}


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_unauthenticated_manifest_fields_can_change_and_bound_fields_cannot(
    tmp_path: Path,
) -> None:
    secret = _key()
    dest = _artifact(tmp_path, secret=secret, relations=["gate2_marker", "other_rel"])
    manifest_path, manifest = _manifest(dest)
    manifest["created_at"] = "2020-01-01T00:00:00Z"
    manifest["tool_version"] = "9.9.9"
    _write_manifest(manifest_path, manifest)
    plain, claims = decrypt_dump(dest, manifest_path, secret, tmp_path / "open")
    assert plain.read_bytes().startswith(b"--")
    assert claims.required_relations == ("gate2_marker", "other_rel")
    assert claims.version == "1"

    manifest["version"] = "0"
    _write_manifest(manifest_path, manifest)
    with pytest.raises(BackupRejectedError, match="version"):
        decrypt_dump(dest, manifest_path, secret, tmp_path / "downgrade-sidecar")

    manifest["version"] = "1"
    manifest["required_relations"] = ["gate2_marker"]
    _write_manifest(manifest_path, manifest)
    with pytest.raises(BackupRejectedError, match="required_relations"):
        decrypt_dump(dest, manifest_path, secret, tmp_path / "relations")


def test_future_schema_and_raw_gzip_downgrade_are_rejected(tmp_path: Path) -> None:
    secret = _key()
    compressed = gzip.compress(DUMP, mtime=0)
    future = tmp_path / "future.sql.gz.enc"
    seal_compressed(
        compressed,
        DUMP,
        secret,
        future,
        database="fixture",
        tool_version="1.3.1",
        schema_version="99",
    )
    with pytest.raises(BackupRejectedError, match="Unsupported backup schema version"):
        decrypt_dump(
            future, future.with_name(future.name + ".manifest.json"), secret, tmp_path / "f"
        )

    old = tmp_path / "old.sql.gz.enc"
    seal_compressed(
        compressed,
        DUMP,
        secret,
        old,
        database="fixture",
        tool_version="1.3.1",
        schema_version="0",
    )
    with pytest.raises(BackupRejectedError, match="Unsupported backup schema version"):
        decrypt_dump(old, old.with_name(old.name + ".manifest.json"), secret, tmp_path / "o")

    current = _artifact(tmp_path / "current", secret=secret)
    manifest_path, manifest = _manifest(current)
    raw = Fernet(secret.encode("ascii")).encrypt(compressed)
    current.write_bytes(raw)
    manifest["ciphertext_sha256"] = hashlib.sha256(raw).hexdigest()
    _write_manifest(manifest_path, manifest)
    with pytest.raises(BackupRejectedError, match="downgraded"):
        decrypt_dump(current, manifest_path, secret, tmp_path / "raw")


def test_bash32_can_parse_restore_script() -> None:
    try:
        bash32 = discover_bash32()
    except Bash32UnavailableError as exc:
        pytest.skip(str(exc))
    except Bash32RejectedError as exc:
        pytest.fail(str(exc))
    assert bash_version(bash32) == (3, 2)
    syntax = subprocess.run(
        [str(bash32), "-n", str(RESTORE)], check=False, capture_output=True, text=True
    )
    assert syntax.returncode == 0, syntax.stderr


def test_origin_aop_harness() -> None:
    script = ROOT / "scripts/cloud/gate2/verify_origin_aop.sh"
    result = subprocess.run(["bash", str(script)], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "AOP_NO_CERT=DENIED" in result.stdout
    assert "AOP_WRONG_CERT=DENIED" in result.stdout
    assert "AOP_VALID_CERT=ALLOWED" in result.stdout
