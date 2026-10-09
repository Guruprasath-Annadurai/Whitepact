# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent check of the origin client-certificate listener and staging gaps."""

from __future__ import annotations

import shutil
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from responsibleai.ops.staging_origin_protection import (
    ENFORCEMENT_ARTIFACTS,
    client_certificate_required,
    missing_artifact_ids,
    origin_client_certificate_enforced,
    origin_protection_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
NGINX = ROOT / "deploy" / "origin" / "nginx-cloudflare-aop.conf"


def test_client_certificate_directive_rejects_optional_and_off() -> None:
    config = NGINX.read_text(encoding="utf-8")
    assert client_certificate_required(config)
    assert "http2 on;" not in config
    assert "listen 443 ssl http2;" in config
    assert (
        client_certificate_required(
            config.replace("ssl_verify_client on;", "ssl_verify_client off;")
        )
        is False
    )
    assert (
        client_certificate_required(
            config.replace("ssl_verify_client on;", "ssl_verify_client optional;")
        )
        is False
    )


def test_staging_origin_artifacts_are_not_claimed_present() -> None:
    inventory = origin_protection_inventory(ROOT)
    missing = set(missing_artifact_ids(inventory))
    expected_missing = {
        "staging_cloudflare_edge_module",
        "staging_authenticated_origin_pulls",
        "per_hostname_aop_certificate_resource",
        "cloudflare_aop_ca_bundle",
        "origin_server_certificate",
        "origin_server_private_key",
        "staging_proxied_dns_record",
        "staging_zone_tls_strict",
        "saas_nginx_package",
        "real_origin_hostname",
    }
    assert expected_missing <= missing
    by_id = {item.artifact_id: item.state for item in inventory}
    assert by_id["origin_nginx_requires_client_certificate"] == "present"
    assert by_id["origin_config_staged_on_saas"] == "present"
    assert by_id["saas_listener_not_started_without_material"] == "present"
    assert origin_client_certificate_enforced(inventory) is False
    assert set(ENFORCEMENT_ARTIFACTS) <= {item.artifact_id for item in inventory}
    main = (ROOT / "infra/terraform/modules/whitepact-hetzner-foundation/main.tf").read_text(
        encoding="utf-8"
    )
    assert main.count('extra_write_files = ""') == 2
    assert "extra_write_files = local.saas_origin_write_files" in main
    assert not (ROOT / "deploy" / "origin" / "server.key").exists()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _openssl(*args: str, timeout: int = 5) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["openssl", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_nginx_origin_config_rejects_missing_and_wrong_client_certificates(tmp_path: Path) -> None:
    if (
        shutil.which("nginx") is None
        or shutil.which("openssl") is None
        or shutil.which("curl") is None
    ):
        pytest.fail("nginx, openssl, and curl are required to validate the origin listener")
    ca_key = tmp_path / "ca.key"
    ca_pem = tmp_path / "ca.pem"
    server_key = tmp_path / "server.key"
    server_csr = tmp_path / "server.csr"
    server_crt = tmp_path / "server.crt"
    good_key = tmp_path / "good.key"
    good_csr = tmp_path / "good.csr"
    good_crt = tmp_path / "good.crt"
    bad_key = tmp_path / "bad.key"
    bad_crt = tmp_path / "bad.crt"
    assert (
        _openssl(
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(ca_key),
            "-out",
            str(ca_pem),
            "-days",
            "1",
            "-nodes",
            "-subj",
            "/CN=WhitePactSyntheticAOP",
        ).returncode
        == 0
    )
    assert (
        _openssl(
            "req",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(server_key),
            "-out",
            str(server_csr),
            "-nodes",
            "-subj",
            "/CN=staging.example.invalid",
            "-addext",
            "subjectAltName=DNS:staging.example.invalid",
        ).returncode
        == 0
    )
    assert (
        _openssl(
            "x509",
            "-req",
            "-in",
            str(server_csr),
            "-CA",
            str(ca_pem),
            "-CAkey",
            str(ca_key),
            "-CAcreateserial",
            "-copy_extensions",
            "copy",
            "-out",
            str(server_crt),
            "-days",
            "1",
        ).returncode
        == 0
    )
    assert (
        _openssl(
            "req",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(good_key),
            "-out",
            str(good_csr),
            "-nodes",
            "-subj",
            "/CN=synthetic-cloudflare-aop",
        ).returncode
        == 0
    )
    assert (
        _openssl(
            "x509",
            "-req",
            "-in",
            str(good_csr),
            "-CA",
            str(ca_pem),
            "-CAkey",
            str(ca_key),
            "-CAcreateserial",
            "-out",
            str(good_crt),
            "-days",
            "1",
        ).returncode
        == 0
    )
    assert (
        _openssl(
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(bad_key),
            "-out",
            str(bad_crt),
            "-days",
            "1",
            "-nodes",
            "-subj",
            "/CN=not-cloudflare",
        ).returncode
        == 0
    )

    port = _free_port()
    upstream = _free_port()

    class _Sentinel(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            body = b"APP_REACHED"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    sentinel = ThreadingHTTPServer(("127.0.0.1", upstream), _Sentinel)
    sentinel_thread = threading.Thread(target=sentinel.serve_forever, daemon=True)
    sentinel_thread.start()
    origin = NGINX.read_text(encoding="utf-8")
    origin = origin.replace("listen 443 ssl http2;", f"listen 127.0.0.1:{port} ssl;")
    origin = origin.replace(
        "proxy_pass http://127.0.0.1:8765;", f"proxy_pass http://127.0.0.1:{upstream};"
    )
    origin = origin.replace("/etc/whitepact/origin/server.crt", str(server_crt))
    origin = origin.replace("/etc/whitepact/origin/server.key", str(server_key))
    origin = origin.replace("/etc/whitepact/origin/cloudflare-aop-ca.pem", str(ca_pem))
    origin_path = tmp_path / "origin.conf"
    origin_path.write_text(origin, encoding="utf-8")
    assert "ssl_verify_client on;" in origin
    prefix = tmp_path / "prefix"
    for name in ("body", "proxy", "fastcgi", "uwsgi", "scgi"):
        (prefix / name).mkdir(parents=True)
    wrapper = tmp_path / "nginx.conf"
    wrapper.write_text(
        "\n".join(
            (
                "worker_processes 1;",
                "daemon off;",
                f"error_log {prefix / 'error.log'};",
                f"pid {prefix / 'nginx.pid'};",
                "events { worker_connections 16; }",
                "http {",
                f"  client_body_temp_path {prefix / 'body'};",
                f"  proxy_temp_path {prefix / 'proxy'};",
                f"  fastcgi_temp_path {prefix / 'fastcgi'};",
                f"  uwsgi_temp_path {prefix / 'uwsgi'};",
                f"  scgi_temp_path {prefix / 'scgi'};",
                f"  access_log {prefix / 'access.log'};",
                f"  include {origin_path};",
                "}",
                "",
            )
        ),
        encoding="utf-8",
    )
    process = subprocess.Popen(
        ["nginx", "-c", str(wrapper), "-p", str(prefix)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        ready = False
        for _ in range(50):
            if process.poll() is not None:
                stderr = process.stderr.read() if process.stderr is not None else ""
                pytest.fail(f"nginx exited before accepting connections: {stderr}")
            with socket.socket() as probe:
                probe.settimeout(0.1)
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    ready = True
                    break
            time.sleep(0.05)
        assert ready

        def request(name: str, *extra: str) -> subprocess.CompletedProcess[str]:
            completed = subprocess.run(
                [
                    "curl",
                    "--http1.1",
                    "--max-time",
                    "5",
                    "--silent",
                    "--show-error",
                    "--cacert",
                    str(ca_pem),
                    "--resolve",
                    f"staging.example.invalid:{port}:127.0.0.1",
                    *extra,
                    f"https://staging.example.invalid:{port}/livez",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            transcript = completed.stdout + "\n" + completed.stderr
            (tmp_path / f"{name}.out").write_text(transcript, encoding="utf-8")
            return completed

        def reaches_app(completed: subprocess.CompletedProcess[str]) -> bool:
            return "APP_REACHED" in completed.stdout

        missing = request("none")
        wrong = request("bad", "--cert", str(bad_crt), "--key", str(bad_key))
        good = request("good", "--cert", str(good_crt), "--key", str(good_key))
        assert reaches_app(missing) is False
        assert reaches_app(wrong) is False
        assert "No required SSL certificate was sent" in (missing.stdout + missing.stderr)
        assert "The SSL certificate error" in (wrong.stdout + wrong.stderr)
        assert reaches_app(good) is True
        assert "No required SSL certificate was sent" not in good.stdout
        assert "The SSL certificate error" not in good.stdout
    finally:
        process.terminate()
        sentinel.shutdown()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
