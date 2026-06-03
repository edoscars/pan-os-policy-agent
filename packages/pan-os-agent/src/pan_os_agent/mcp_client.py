"""Async MCP client: spawns the pan-os-mcp server over stdio and calls its tools.

The agent is a real MCP *client* — it runs the server as a subprocess and talks
to it over the protocol, rather than importing the tool functions directly. This
is the production-realistic path; the template is pan-os-mcp's smoke_test.py.
"""

import json
import os
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
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
    """Async context manager around a spawned pan-os-mcp server session.

    The session is opened once on __aenter__ and reused across call_tool
    invocations, so the firewall connection (lru_cached server-side) is not
    torn down between calls. Pass an explicit env to forward credentials to
    the subprocess; defaults to the current process environment, which is
    populated when the agent is run via `uv run --env-file .env`.
    """

    def __init__(self, env: dict[str, str] | None = None) -> None:
        self._env = env if env is not None else dict(os.environ)
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "McpClient":
        params = StdioServerParameters(
            command="uv",
            args=["run", "pan-os-mcp"],
            env=self._env,
        )
        self._stack = AsyncExitStack()
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
