"""FastMCP server registering pan-os-mcp tools."""

import os

from mcp.server.fastmcp import FastMCP

from pan_os_mcp.tools.system import register as register_system_tools
from pan_os_mcp.tools.network import register as register_network_tools
from pan_os_mcp.tools.objects import register as object_network_tools
from pan_os_mcp.tools.policies import register as register_policy_tools

mcp = FastMCP("pan-os-mcp")

# Register tools by feature area.
register_system_tools(mcp)
register_network_tools(mcp)
object_network_tools(mcp)
register_policy_tools(mcp)

def main() -> None:
    """Entry point referenced by [project.scripts] in pyproject.toml.

    Defaults to stdio — how the agent's McpClient spawns it. Set
    PAN_OS_MCP_TRANSPORT=streamable-http to instead serve it over HTTP (at
    http://127.0.0.1:8000/mcp by default; override host/port with FASTMCP_HOST
    / FASTMCP_PORT), e.g. to register it behind the Portkey MCP gateway.
    """
    mcp.run(transport=os.getenv("PAN_OS_MCP_TRANSPORT", "stdio"))

if __name__ == "__main__":
    main()