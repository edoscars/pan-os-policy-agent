"""Shared helper for schema-validated structured-output calls to Claude.

Every stage that needs Claude's judgment goes through complete_structured. Using
the SDK's messages.parse (output_format=<model>) constrains the response to a
Pydantic schema and returns a validated instance, so stages never hand-parse
JSON or guard against malformed output — the schema does that work.
"""

from typing import TypeVar

from anthropic import APIStatusError
from pydantic import BaseModel

from pan_os_agent.context import AgentContext

T = TypeVar("T", bound=BaseModel)

# Generous ceiling for a single structured stage result. Stage outputs are small
# structured objects, not prose, so this is rarely approached.
MAX_TOKENS = 4096

# Portkey returns HTTP 446 when a gateway guardrail denies a call — e.g. the
# Prisma AIRS guardrail blocking the input prompt (before the model runs) or the
# output. The AIRS profile + key live in Portkey, not here. See Portkey docs.
GUARDRAIL_DENIED_STATUS = 446


class GuardrailBlocked(Exception):
    """Raised when the LLM gateway's guardrail denied a call (HTTP 446)."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(detail or "gateway guardrail denied the request")
        self.detail = detail


def _guardrail_detail(exc: APIStatusError) -> str:
    """Best-effort short message; the full AIRS verdict is in the Portkey/AIRS logs."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        message = body.get("message") or body.get("error", {}).get("message")
        if message:
            return str(message)[:200]
    return ""


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
    try:
        response = await ctx.anthropic.messages.parse(
            model=ctx.model,
            max_tokens=MAX_TOKENS,
            system=[
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
    except APIStatusError as exc:
        if exc.status_code == GUARDRAIL_DENIED_STATUS:
            raise GuardrailBlocked(_guardrail_detail(exc)) from exc
        raise

    if response.stop_reason == "refusal":
        return None
    return response.parsed_output
