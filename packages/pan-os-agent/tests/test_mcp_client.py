"""Tests for pan_os_agent.mcp_client result parsing.

Tests the layer this package owns — turning a CallToolResult into usable data
and raising on tool errors — using real mcp.types objects, no live server.
"""

import pytest
from mcp.types import CallToolResult, TextContent

from pan_os_agent.mcp_client import McpToolError, _parse_tool_result


def _result(*, content, structured, is_error=False) -> CallToolResult:
    return CallToolResult(
        content=content,
        structuredContent=structured,
        isError=is_error,
    )


def test_parse_scalar_tool_returns_object_dict():
    """A scalar tool (get_system_info) yields its flat structuredContent dict."""
    result = _result(
        content=[TextContent(type="text", text='{"model": "PA-440"}')],
        structured={"model": "PA-440", "hostname": "PA-440"},
    )

    parsed = _parse_tool_result("get_system_info", result)

    assert parsed == {"model": "PA-440", "hostname": "PA-440"}


def test_parse_list_tool_wraps_under_result_key():
    """A list tool (list_zones) wraps its list under "result" per the MCP spec."""
    result = _result(
        content=[TextContent(type="text", text="{}")],
        structured={"result": [{"name": "trust"}, {"name": "untrust"}]},
    )

    parsed = _parse_tool_result("list_zones", result)

    assert parsed["result"] == [{"name": "trust"}, {"name": "untrust"}]


def test_parse_raises_on_tool_error():
    """isError surfaces as McpToolError with the error text included."""
    result = _result(
        content=[TextContent(type="text", text="boom: no such object")],
        structured=None,
        is_error=True,
    )

    with pytest.raises(McpToolError, match="boom: no such object"):
        _parse_tool_result("get_rule_by_name", result)


def test_parse_falls_back_to_text_json_when_no_structured_content():
    """When structuredContent is absent, parse JSON from the first text block."""
    result = _result(
        content=[TextContent(type="text", text='{"ok": true}')],
        structured=None,
    )

    parsed = _parse_tool_result("some_tool", result)

    assert parsed == {"ok": True}
