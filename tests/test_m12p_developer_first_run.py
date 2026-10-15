# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Offline preflight safety; fixtures below are synthetic, never credentials."""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "m12p_first_run", Path(__file__).parents[1] / "scripts/developer/first_run.py"
)
assert SPEC and SPEC.loader
doctor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(doctor)


def configured():
    return {
        "WHITEPACT_DATABASE_URL": "postgresql://local:synthetic@127.0.0.1:55432/wp_test",
        "WHITEPACT_REDIS_URL": "redis://127.0.0.1:56379/0",
        "WHITEPACT_API_KEYS": "synthetic-private-test-marker",
    }


def report(env):
    return doctor.inspect_environment(
        env,
        executables=dict.fromkeys(("git", "docker", "node", "npm"), True),
        python_version=(3, 11),
    )


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_explicit_loopback_is_accepted_without_readiness_claim(host):
    env = configured()
    env["WHITEPACT_DATABASE_URL"] = f"postgresql://u:synthetic@{host}/db"
    result = report(env)
    assert result["configuration_preflight"] == "PASS"
    assert result["connections_tested"] is False
    assert result["customer_execution_ready"] is False
    assert result["production_ready"] is False


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@db.supabase.co/db",
        "postgresql://u:p@10.0.0.1/db",
        "postgresql://u:p@localhost.evil.test/db",
        "postgresql://u:p@2130706433/db",
        "postgresql://u:p@127.0.0.1/db?host=production.example",
        "postgresql://u:p@localhost/db#x",
        "postgresql://localhost/db",
        "postgresql://u:p@[::1/db",
        "postgresql://u:p@localhost:0/db",
        "postgresql://u:p@localhost:999999/db",
        "postgresql://u:p@local%68ost/db",
        " postgresql://u:p@localhost/db",
        "postgresql://u:p@localhost/db\n",
        "sqlite:///db",
    ],
)
def test_unsafe_database_url_rejected(url):
    env = configured()
    env["WHITEPACT_DATABASE_URL"] = url
    assert report(env)["configuration_preflight"] == "BLOCKED"


@pytest.mark.parametrize(
    "url",
    [
        "redis://redis.upstash.io/0",
        "redis://localhost/0?host=evil",
        "redis://localhost/-1",
        "redis://localhost/0/x",
    ],
)
def test_unsafe_redis_rejected(url):
    env = configured()
    env["WHITEPACT_REDIS_URL"] = url
    assert report(env)["configuration_preflight"] == "BLOCKED"


@pytest.mark.parametrize(
    "key,value",
    [
        ("DATABASE_URL", "postgresql://u:p@production.example/db"),
        ("RAI_REDIS_URL", "redis://remote.example/0"),
        ("RAI_AUTH_ENABLED", "false"),
        ("WHITEPACT_AUTH_ENABLED", "false"),
        ("PHASE7A_DISPATCHER_ENABLED", "true"),
        ("RAI_PHASE7A_DISPATCHER_ENABLED", "true"),
        ("WHITEPACT_ENV", "production"),
        ("RAI_ENV", "production"),
    ],
)
def test_shadowed_unsafe_alias_also_blocks(key, value):
    env = configured()
    env[key] = value
    assert report(env)["configuration_preflight"] == "BLOCKED"


def test_missing_prerequisites_and_old_python_block():
    result = doctor.inspect_environment({}, executables={}, python_version=(3, 10))
    assert result["configuration_preflight"] == "BLOCKED"
    assert result["checks"]["python_3_11_or_newer"] == "FAIL"
    assert result["checks"]["docker_on_path"] == "MISSING"


def test_no_environment_values_or_unknown_variable_names_emitted():
    env = configured()
    env["UNRELATED_SECRET_MARKER"] = "another-private-marker"
    encoded = json.dumps(report(env))
    for value in env.values():
        assert value not in encoded
    assert "UNRELATED_SECRET_MARKER" not in encoded


def test_cli_exit_and_output_are_sanitized(monkeypatch, capsys):
    monkeypatch.setattr(
        doctor.os, "environ", {"DATABASE_URL": "postgresql://secret-user:secret-pass@[bad"}
    )
    assert doctor.main() == 2
    output = capsys.readouterr().out
    assert json.loads(output)["configuration_preflight"] == "BLOCKED"
    assert "secret" not in output
    assert "Traceback" not in output


def test_lowercase_settings_are_not_ignored():
    env = {key.lower(): value for key, value in configured().items()}
    assert report(env)["configuration_preflight"] == "PASS"
    env["rai_auth_enabled"] = "false"
    assert report(env)["configuration_preflight"] == "BLOCKED"


def test_conflicting_case_aliases_rejected():
    env = configured()
    env["whitepact_database_url"] = "postgresql://u:p@remote.example/db"
    assert report(env)["checks"]["case_insensitive_aliases_unambiguous"] == "FAIL"


def test_preflight_never_connects_or_mutates_environment(monkeypatch):
    import socket
    import subprocess

    def forbidden(*args, **kwargs):
        pytest.fail("offline diagnostic attempted network or process execution")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    env = configured()
    before = env.copy()
    assert report(env)["configuration_preflight"] == "PASS"
    assert env == before


def test_quickstart_install_extras_and_postgres_image_match_repository():
    import tomllib

    root = Path(__file__).parents[1]
    guide = (root / "docs/developer/M12P_LOCAL_FIRST_RUN.md").read_text()
    project = tomllib.loads((root / "pyproject.toml").read_text())
    extras = project["project"]["optional-dependencies"]
    assert all(name in extras for name in ("dashboard", "postgres", "redis"))
    assert any("asyncpg" in dependency for dependency in extras["postgres"])
    assert "pip install -e '.[dashboard,postgres,redis]'" in guide
    assert "pip install -e ./sdk/python" in guide
    workflow = (root / ".github/workflows/ci.yml").read_text()
    image = next(
        line.split("image:", 1)[1].strip()
        for line in workflow.splitlines()
        if "image: postgres:" in line
    )
    assert image in guide
    assert "127.0.0.1:55439:5432" in guide
    assert "--env-file" in guide and "chmod 600" in guide


@pytest.mark.parametrize("value", [",", " , , ", "", "   "])
def test_comma_only_api_keys_do_not_count_as_configured(value):
    env = configured()
    env["WHITEPACT_API_KEYS"] = value
    assert report(env)["checks"]["api_key_configured"] == "MISSING"


def test_empty_canonical_key_does_not_fall_back_to_shadowed_legacy_key():
    env = configured()
    env["WHITEPACT_API_KEYS"] = ""
    env["RAI_API_KEYS"] = "synthetic-shadowed"
    assert report(env)["checks"]["api_key_configured"] == "MISSING"


def test_json_looking_key_is_literal_under_actual_server_csv_contract():
    env = configured()
    env["WHITEPACT_API_KEYS"] = "[]"
    # Settings._parse_keys uses NoDecode and CSV, not JSON-array decoding.
    assert report(env)["checks"]["api_key_configured"] == "PASS"
