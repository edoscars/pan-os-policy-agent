"""Direct smoke test for the pan-os-mcp server.

Spawns the server as a subprocess over stdio, lists tools,
and invokes get_system_info. Prints the result.
"""

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import os
from pathlib import Path
from dotenv import dotenv_values

# Load .env from repo root
repo_root = Path(__file__).resolve().parents[3]
env_vars = dotenv_values(repo_root / ".env")

full_env = {**os.environ, **env_vars}

async def main() -> None:
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "pan-os-mcp"],
        env=full_env,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List the tools the server exposes
            tools = await session.list_tools()
            print("Registered tools:")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")

            # Invoke get_system_info
            print("\nCalling get_system_info...")
            result = await session.call_tool("get_system_info", {})
            print(result)

            print("\nCalling list_zones()")
            result = await session.call_tool("list_zones", {})
            print(result)


if __name__ == "__main__":
    asyncio.run(main())