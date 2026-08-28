from __future__ import annotations

from types import SimpleNamespace

import pytest

from responsibleai.integrations.gemini_mcp_bridge import GeminiMCPBridge


class _FakeSession:
    async def list_tools(self):
        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="rai_scan",
                    description="Scan text",
                    inputSchema={
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                )
            ]
        )

    async def call_tool(self, name, arguments):
        assert name == "rai_scan"
        assert arguments == {"text": "hello"}
        return SimpleNamespace(
            isError=False,
            structuredContent={"safe": True},
            content=[SimpleNamespace(type="text", text='{"safe": true}')],
        )


class _ErrorSession(_FakeSession):
    async def call_tool(self, name, arguments):
        return SimpleNamespace(
            isError=True,
            structuredContent=None,
            content=[SimpleNamespace(type="text", text="denied")],
        )


async def test_lists_gemini_function_declarations_from_mcp_schema() -> None:
    bridge = GeminiMCPBridge(_FakeSession())
    declarations = await bridge.list_function_declarations()
    assert declarations == [
        {
            "name": "rai_scan",
            "description": "Scan text",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        }
    ]


async def test_call_returns_structured_content_when_available() -> None:
    bridge = GeminiMCPBridge(_FakeSession())
    assert await bridge.call("rai_scan", {"text": "hello"}) == {"safe": True}


async def test_call_falls_back_to_text_content() -> None:
    session = _FakeSession()

    async def text_only(name, arguments):
        return SimpleNamespace(
            isError=False,
            structuredContent=None,
            content=[SimpleNamespace(type="text", text="ok")],
        )

    session.call_tool = text_only
    assert await GeminiMCPBridge(session).call("rai_scan", {}) == {"content": ["ok"]}


async def test_mcp_error_is_not_silently_returned_as_success() -> None:
    with pytest.raises(RuntimeError, match="denied"):
        await GeminiMCPBridge(_ErrorSession()).call("rai_scan", {})
