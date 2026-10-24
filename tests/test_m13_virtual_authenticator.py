# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual Chromium ceremonies verified by production cryptographic functions.

This does not establish a customer session, bootstrap, tenant or root authority.
Browser dependencies are mandatory: missing Chromium is a failure, not a skip.
"""

import json
import secrets
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from responsibleai.enterprise.security.webauthn import (
    FLAG_UP,
    FLAG_UV,
    b64url_decode,
    b64url_encode,
    verify_assertion,
    verify_registration,
)


@pytest.fixture(scope="module")
def browser_ceremony():
    class Page(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<!doctype html><title>Isolated WebAuthn ceremony</title>")

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Page) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        config = {
            "origin": f"http://localhost:{server.server_port}",
            "registrationChallenge": b64url_encode(secrets.token_bytes(32)),
            "authenticationChallenge": b64url_encode(secrets.token_bytes(32)),
            "userId": b64url_encode(secrets.token_bytes(32)),
        }
        assert config["registrationChallenge"] != config["authenticationChallenge"]
        try:
            run = subprocess.run(
                ["node", str(Path(__file__).parent / "js/m13-virtual-authenticator.mjs")],
                input=json.dumps(config),
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            assert run.returncode == 0, run.stderr
            yield config, json.loads(run.stdout)
        finally:
            server.shutdown()
            worker.join(timeout=5)
            assert not worker.is_alive()


def _registration(config, result, **changes):
    fields = {
        "client_data_b64": result["registration"]["client_data_b64"],
        "authenticator_data_b64": result["registration"]["authenticator_data_b64"],
        "expected_origin": config["origin"],
        "expected_rp_id": "localhost",
        "expected_challenge": b64url_decode(config["registrationChallenge"]),
        "require_uv": True,
    }
    return verify_registration(**(fields | changes))


def test_real_virtual_registration_and_authentication(browser_ceremony):
    config, result = browser_ceremony
    credential, public_key, count, flags = _registration(config, result)
    assert b64url_encode(credential) == result["registration"]["id"]
    assert flags & FLAG_UP and flags & FLAG_UV
    assertion = {key: value for key, value in result["assertion"].items() if key != "id"}
    arguments = dict(
        **assertion,
        public_key_uncompressed=public_key,
        expected_type="webauthn.get",
        expected_origin=config["origin"],
        expected_rp_id="localhost",
        expected_challenge=b64url_decode(config["authenticationChallenge"]),
        require_uv=True,
    )
    next_count = verify_assertion(**arguments, previous_sign_count=count)
    assert next_count > count
    with pytest.raises(ValueError, match="sign count did not advance"):
        verify_assertion(**arguments, previous_sign_count=next_count)
    with pytest.raises(ValueError, match="signature invalid"):
        verify_assertion(
            **(arguments | {"signature_b64": b64url_encode(b"invalid")}), previous_sign_count=count
        )


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("expected_origin", "http://other.invalid", "origin mismatch"),
        ("expected_rp_id", "other.invalid", "RP ID hash mismatch"),
        ("expected_challenge", b"wrong challenge", "challenge mismatch"),
    ],
)
def test_browser_registration_rejects_wrong_binding(browser_ceremony, field, value, reason):
    config, result = browser_ceremony
    with pytest.raises(ValueError, match=reason):
        _registration(config, result, **{field: value})


@pytest.mark.parametrize("flag,reason", [(FLAG_UP, "user-present"), (FLAG_UV, "user verification")])
def test_browser_registration_rejects_missing_flags(browser_ceremony, flag, reason):
    config, result = browser_ceremony
    data = bytearray(b64url_decode(result["registration"]["authenticator_data_b64"]))
    data[32] &= ~flag  # Explicit negative mutation; never used as positive ceremony evidence.
    with pytest.raises(ValueError, match=reason):
        _registration(config, result, authenticator_data_b64=b64url_encode(bytes(data)))


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("expected_origin", "http://other.invalid", "origin mismatch"),
        ("expected_rp_id", "other.invalid", "RP ID hash mismatch"),
        ("expected_challenge", b"wrong challenge", "challenge mismatch"),
    ],
)
def test_browser_assertion_rejects_wrong_binding(browser_ceremony, field, value, reason):
    config, result = browser_ceremony
    _, public_key, count, _ = _registration(config, result)
    assertion = {key: value for key, value in result["assertion"].items() if key != "id"}
    arguments = dict(
        **assertion,
        public_key_uncompressed=public_key,
        expected_type="webauthn.get",
        expected_origin=config["origin"],
        expected_rp_id="localhost",
        expected_challenge=b64url_decode(config["authenticationChallenge"]),
        require_uv=True,
        previous_sign_count=count,
    )
    with pytest.raises(ValueError, match=reason):
        verify_assertion(**(arguments | {field: value}))
