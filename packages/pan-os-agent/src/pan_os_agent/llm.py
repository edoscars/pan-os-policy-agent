"""Shared helper for schema-validated structured-output calls to Claude.

Every stage that needs Claude's judgment goes through complete_structured. Using
the SDK's messages.parse (output_format=<model>) constrains the response to a
Pydantic schema and returns a validated instance, so stages never hand-parse
JSON or guard against malformed output — the schema does that work.
"""

from typing import TypeVar

from pydantic import BaseModel

from pan_os_agent.context import AgentContext

T = TypeVar("T", bound=BaseModel)

# Generous ceiling for a single structured stage result. Stage outputs are small
# structured objects, not prose, so this is rarely approached.
MAX_TOKENS = 4096


async def complete_structured(
    ctx: AgentContext,
    *,
    system: str,
    user: str,
    schema: type[T],
) -> T | None:
    """Return a schema-validated result from Claude, or None if it refused.

    The system prompt is sent as a cache-controlled block: it's the stable part
    of a stage (identical across every fixture), so caching it makes every call
    after the first cheaper. The per-intent data goes in the user turn, after
    the cache breakpoint, so it doesn't invalidate the cached prefix.
    """
    response = await ctx.anthropic.messages.parse(
        model=ctx.model,
        max_tokens=MAX_TOKENS,
        system=[
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ],
        messages=[{"role": "user", "content": user}],
        output_format=schema,
    )
    if response.stop_reason == "refusal":
        return None
    return response.parsed_output
