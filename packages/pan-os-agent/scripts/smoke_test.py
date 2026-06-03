"""Integration smoke test for the agent's McpClient.

Spawns the pan-os-mcp server via McpClient and calls the three existing tools
against the live firewall. Manual check (needs a reachable PA-440 + creds in
the environment), not a unit test.

Run from repo root:
    uv run --env-file .env python packages/pan-os-agent/scripts/smoke_test.py
"""

import asyncio

from pan_os_agent.mcp_client import McpClient


async def main() -> None:
    async with McpClient() as mcp:
        print("Calling get_system_info...")
        print(await mcp.call_tool("get_system_info"))

        print("\nCalling list_zones...")
        zones = await mcp.call_tool("list_zones")
        for zone in zones["result"]:
            print(f"  - {zone['name']} ({zone['mode']})")

        print("\nCalling list_address_objects...")
        objs = await mcp.call_tool("list_address_objects")
        for obj in objs["result"]:
            print(f"  - {obj['name']} = {obj['value']} ({obj['type']})")


if __name__ == "__main__":
    asyncio.run(main())
