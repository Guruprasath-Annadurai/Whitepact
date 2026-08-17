"""Tests for dashboard.middleware -- previously untested in isolation (only
exercised incidentally through full app.py integration tests, which never
hit every branch). Builds minimal Starlette/FastAPI apps directly around
each middleware/dependency/handler so every conditional is exercised without
booting the full dashboard app."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from responsibleai.dashboard.middleware import (
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    build_api_key_dependency,
    global_exception_handler,
    http_exception_handler,
)


class TestRequestIDMiddleware:
    def test_adds_request_id_header(self):
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/x")
        def _handler():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/x")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) == 8


class TestSecurityHeadersMiddleware:
    def test_injects_all_security_headers(self):
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/x")
        def _handler():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/x")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in resp.headers
        assert "Strict-Transport-Security" in resp.headers


class TestRequestLoggingMiddleware:
    def test_adds_response_time_header(self):
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/x")
        def _handler():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/x")
        assert "X-Response-Time-Ms" in resp.headers

    def test_logs_without_request_id_state_set(self):
        # RequestLoggingMiddleware alone (no RequestIDMiddleware ahead of it)
        # exercises the getattr(..., "?") fallback branch.
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/x")
        def _handler():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/x")
        assert resp.status_code == 200


class TestBuildApiKeyDependency:
    def _client_for(self, api_keys, enabled):
        app = FastAPI()
        dep = build_api_key_dependency(api_keys, enabled)

        @app.get("/protected", dependencies=[__import__("fastapi").Depends(dep)])
        def _handler():
            return {"ok": True}

        return TestClient(app)

    def test_disabled_auth_allows_request_without_header(self):
        client = self._client_for(["k1"], enabled=False)
        resp = client.get("/protected")
        assert resp.status_code == 200

    def test_enabled_but_no_keys_configured_allows_request(self):
        client = self._client_for([], enabled=True)
        resp = client.get("/protected")
        assert resp.status_code == 200

    def test_missing_authorization_header_rejected(self):
        client = self._client_for(["k1"], enabled=True)
        resp = client.get("/protected")
        assert resp.status_code == 401

    def test_malformed_authorization_header_rejected(self):
        client = self._client_for(["k1"], enabled=True)
        resp = client.get("/protected", headers={"Authorization": "Basic abc"})
        assert resp.status_code == 401

    def test_invalid_key_rejected(self):
        client = self._client_for(["k1"], enabled=True)
        resp = client.get("/protected", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 403

    def test_valid_key_accepted(self):
        client = self._client_for(["k1", "k2"], enabled=True)
        resp = client.get("/protected", headers={"Authorization": "Bearer k2"})
        assert resp.status_code == 200


class TestGlobalExceptionHandler:
    async def test_returns_500_with_request_id(self):
        app = FastAPI()

        async def _dummy_endpoint(request: Request):
            return None

        request = Request(
            scope={
                "type": "http",
                "method": "GET",
                "path": "/boom",
                "headers": [],
                "app": app,
            }
        )
        request.state.request_id = "abc123"
        resp = await global_exception_handler(request, ValueError("boom"))
        assert resp.status_code == 500
        assert resp.body
        import json

        body = json.loads(resp.body)
        assert body["request_id"] == "abc123"

    async def test_falls_back_to_unknown_request_id(self):
        app = FastAPI()
        request = Request(
            scope={"type": "http", "method": "GET", "path": "/boom", "headers": [], "app": app}
        )
        resp = await global_exception_handler(request, RuntimeError("x"))
        import json

        body = json.loads(resp.body)
        assert body["request_id"] == "?"


class TestHttpExceptionHandler:
    async def test_returns_status_code_and_detail(self):
        app = FastAPI()
        request = Request(
            scope={"type": "http", "method": "GET", "path": "/x", "headers": [], "app": app}
        )
        request.state.request_id = "rid-1"
        exc = HTTPException(status_code=404, detail="not found")
        resp = await http_exception_handler(request, exc)
        assert resp.status_code == 404
        import json

        body = json.loads(resp.body)
        assert body["message"] == "not found"
        assert body["request_id"] == "rid-1"

    async def test_includes_headers_when_present(self):
        app = FastAPI()
        request = Request(
            scope={"type": "http", "method": "GET", "path": "/x", "headers": [], "app": app}
        )
        exc = HTTPException(status_code=401, detail="nope", headers={"WWW-Authenticate": "Bearer"})
        resp = await http_exception_handler(request, exc)
        assert resp.headers.get("www-authenticate") == "Bearer"
