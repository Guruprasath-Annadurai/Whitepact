# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Public MCP metadata and a real loopback HTTP consumer; no provider approval claim."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from responsibleai.integrations.client import TrustClient
from responsibleai.mcp import tools


def test_public_trust_lookup_declares_its_external_network_boundary():
    tool = next(item for item in tools.PRODUCTION_TOOL_DEFS if item.name == "rai_check_trust")
    assert tool.annotations.openWorldHint is True
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False
    assert "advisory" in tool.description.lower()


@pytest.mark.asyncio
async def test_public_trust_lookup_really_reads_its_configured_http_service(monkeypatch):
    observed = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            observed.append(self.path)
            body = json.dumps({"known": False, "certified": False}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        monkeypatch.setattr(
            tools, "_trust_client", TrustClient(f"http://127.0.0.1:{server.server_port}")
        )
        try:
            result = await tools.dispatch_tool(
                "rai_check_trust", {"model_name": "local-model", "provider": "local-provider"}
            )
            assert result["known"] is False
            assert result["certified"] is False
            assert result["passes"] is False
            assert observed == ["/api/trust-index/check?model=local-model&provider=local-provider"]
        finally:
            server.shutdown()
            worker.join(timeout=2)
            assert not worker.is_alive()
