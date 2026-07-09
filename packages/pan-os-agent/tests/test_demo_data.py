"""Tests for the demo-mode canned firewall.

Demo mode ships in the product (not just tests), so its contract is covered:
DemoMcpClient must be a drop-in for McpClient — same async-context + call_tool
surface — and return the {"result": [...]} shape the stages unwrap.
"""

import pytest

from pan_os_agent.demo_data import DemoMcpClient

INVENTORY_TOOLS = [
    "list_zones",
    "list_address_objects",
    "list_address_groups",
    "list_services",
    "list_security_rules",
]


async def test_demo_client_is_async_context_manager():
    async with DemoMcpClient() as mcp:
        result = await mcp.call_tool("list_zones")
    assert "result" in result


@pytest.mark.parametrize("tool", INVENTORY_TOOLS)
async def test_list_tools_return_wrapped_list(tool):
    async with DemoMcpClient() as mcp:
        result = await mcp.call_tool(tool)
    assert isinstance(result["result"], list)
    assert all("name" in item for item in result["result"])


async def test_get_system_info_returns_flat_object():
    async with DemoMcpClient() as mcp:
        info = await mcp.call_tool("get_system_info")
    assert info["model"] == "PA-440"
    assert "hostname" in info


async def test_unknown_tool_raises():
    async with DemoMcpClient() as mcp:
        with pytest.raises(KeyError):
            await mcp.call_tool("commit_config")


async def test_rulebase_has_a_broad_outbound_rule_for_shadowing_demos():
    async with DemoMcpClient() as mcp:
        rules = (await mcp.call_tool("list_security_rules"))["result"]
    names = {r["name"] for r in rules}
    assert "allow-all-outbound" in names
