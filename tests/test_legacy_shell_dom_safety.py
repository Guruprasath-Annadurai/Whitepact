# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The community app still serves the retired governance shell (unified/production mode does not).

CodeQL alerts 121-132 were real: ``escHtml`` left quotes alone while its output was placed inside
HTML attributes, and the login ``next`` parameter was assigned to ``location.href`` unchecked.
These tests execute the shipped JavaScript with Node against hostile input, so a regression in the
page source fails here instead of relying on a static pattern match.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SHELL = (
    Path(__file__).resolve().parents[1]
    / "src/responsibleai/dashboard/legacy_templates/governance_shell"
)
NODE = shutil.which("node")


def _extract(html: str, name: str) -> str:
    match = re.search(rf"^  function {name}\(.*?^  }}\n", html, re.S | re.M)
    assert match, f"{name} not found"
    return match.group(0)


def _run(source: str, expression: str) -> object:
    assert NODE, "node is required to execute the legacy shell JavaScript"
    result = subprocess.run(  # noqa: S603
        [NODE, "-e", f"{source}\nprocess.stdout.write(JSON.stringify({expression}));"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


ESC_PAGES = sorted(p for p in SHELL.glob("*.html") if "function escHtml" in p.read_text())

HOSTILE = [
    '" onmouseover="alert(1)',
    "' onfocus='alert(1)",
    "<img src=x onerror=alert(1)>",
    "&quot;",
]


def test_every_page_that_defines_escHtml_was_found() -> None:
    assert len(ESC_PAGES) >= 15


@pytest.mark.parametrize("page", ESC_PAGES, ids=lambda p: p.name)
def test_escHtml_neutralises_attribute_and_tag_breakout(page: Path) -> None:
    fn = _extract(page.read_text(), "escHtml")
    out = _run(fn, f"{json.dumps(HOSTILE)}.map(escHtml)")
    assert isinstance(out, list)
    for original, escaped in zip(HOSTILE, out, strict=True):
        assert '"' not in escaped and "'" not in escaped and "<" not in escaped, escaped
        assert ">" not in escaped
        assert escaped != original
    # & is escaped first, so an entity in the input is not interpreted by the browser.
    assert out[-1] == "&amp;quot;"


def _login_helpers() -> str:
    html = (SHELL / "login.html").read_text()
    return _extract(html, "safeNext") + _extract(html, "safeHttpUrl")


@pytest.mark.parametrize(
    "value",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "//evil.example/x",
        "/\\evil.example/x",
        "https://evil.example/",
        "evil",
        "/\t/evil.example",
        "/\n/evil.example",
        "",
        None,
    ],
)
def test_login_next_rejects_everything_but_a_same_origin_path(value: object) -> None:
    assert _run(_login_helpers(), f"safeNext({json.dumps(value)})") == "/"


@pytest.mark.parametrize("value", ["/dashboard", "/audit?days=30", "/a/b#c"])
def test_login_next_keeps_legitimate_paths(value: str) -> None:
    assert _run(_login_helpers(), f"safeNext({json.dumps(value)})") == value


@pytest.mark.parametrize(
    "value", ["javascript:alert(1)", "data:text/html,x", "vbscript:x", "file:///etc/passwd"]
)
def test_sso_redirect_target_must_be_http_or_https(value: str) -> None:
    helpers = _login_helpers()
    assert (
        _run(
            "const window={location:{origin:'https://app.example'}};" + helpers,
            f"safeHttpUrl({json.dumps(value)})",
        )
        is None
    )


def test_sso_redirect_accepts_https_provider() -> None:
    helpers = _login_helpers()
    got = _run(
        "const window={location:{origin:'https://app.example'}};" + helpers,
        "safeHttpUrl('https://idp.example/authorize?x=1')",
    )
    assert got == "https://idp.example/authorize?x=1"


def test_navigation_sinks_in_the_shell_are_guarded() -> None:
    login = (SHELL / "login.html").read_text()
    assert login.count("window.location.href = nextUrl") == 2
    assert 'const nextUrl = safeNext(params.get("next"));' in login
    assert "window.location.href = d.authorization_url" not in login
    billing = (SHELL / "billing.html").read_text()
    assert "window.location.href = d2.checkout_url" not in billing
    settings = (SHELL / "settings.html").read_text()
    assert r"/^https?:\/\//i.test(String(d.changelog_url))" in settings
