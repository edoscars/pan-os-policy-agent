"""FastMCP server registering pan-os-mcp tools."""

from mcp.server.fastmcp import FastMCP

from pan_os_mcp.tools.system import register as register_system_tools

mcp = FastMCP("pan-os-mcp")

# Register tools by feature area.
register_system_tools(mcp)

def main() -> None:
    """Entry point referenced by [project.scripts] in pyproject.toml."""
    mcp.run()

if __name__ == "__main__":
    main()