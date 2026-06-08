"""Async MCP client: talks to the pan-os-mcp tools over the MCP protocol.

The agent is a real MCP *client*. By default it spawns the pan-os-mcp server as
a subprocess over stdio. If a `url` is given, it instead connects to that remote
streamable-HTTP endpoint — e.g. the Portkey MCP gateway
(https://mcp.portkey.ai/<slug>/mcp), so every tool call is proxied and logged by
Portkey. Either way the rest of the agent is unchanged.
"""

import json
import os
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult


class McpToolError(RuntimeError):
    """Raised when an MCP tool call comes back with isError set."""


def _parse_tool_result(name: str, result: CallToolResult) -> Any:
    """Extract usable data from a CallToolResult, or raise on tool error.

    FastMCP returns structured output as `structuredContent`: a flat dict for
    scalar/object tools (e.g. get_system_info), and `{"result": [...]}` for
    list tools (the MCP spec requires structured content to be a JSON object,
    so lists get wrapped). Callers unwrap the "result" key for list tools.

    Falls back to JSON-parsing the first text block if structuredContent is
    absent. This is the layer this package owns, so it gets the unit test.
    """
    if result.isError:
        detail = result.content[0].text if result.content else "unknown error"
        raise McpToolError(f"tool {name!r} failed: {detail}")

    if result.structuredContent is not None:
        return result.structuredContent

    if result.content and getattr(result.content[0], "text", None) is not None:
        return json.loads(result.content[0].text)

    raise McpToolError(f"tool {name!r} returned no parseable content")


class McpClient:
    """Async context manager around an MCP session, reused across call_tool.

    Two transports, chosen by `url`:
      - `url=""` (default): spawn pan-os-mcp over stdio. `env` is forwarded to the
        subprocess (defaults to the current environment, populated by
        `uv run --env-file .env`).
      - `url` set: connect to a remote streamable-HTTP endpoint with `headers`
        (e.g. the Portkey MCP gateway, with x-portkey-api-key), so tool calls are
        governed and logged by Portkey.
    """

    def __init__(
        self,
        env: dict[str, str] | None = None,
        url: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self._env = env if env is not None else dict(os.environ)
        self._url = url
        self._headers = headers or {}
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "McpClient":
        self._stack = AsyncExitStack()
        if self._url:
            # streamablehttp_client yields (read, write, get_session_id).
            read, write, _ = await self._stack.enter_async_context(
                streamablehttp_client(self._url, headers=self._headers)
            )
        else:
            params = StdioServerParameters(
                command="uv", args=["run", "pan-os-mcp"], env=self._env
            )
            read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def call_tool(self, name: str, arguments: dict | None = None) -> Any:
        """Call an MCP tool and return its parsed structured content.

        Raises McpToolError if the session isn't open or the tool errored.
        """
        if self._session is None:
            raise McpToolError("McpClient used outside its async context")
        result = await self._session.call_tool(name, arguments or {})
        return _parse_tool_result(name, result)
