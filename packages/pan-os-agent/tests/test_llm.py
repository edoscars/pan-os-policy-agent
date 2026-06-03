"""Tests for the complete_structured LLM helper."""

from pan_os_agent.context import AgentContext
from pan_os_agent.llm import complete_structured
from pan_os_agent.models import StructuredIntent


def _ctx(anthropic) -> AgentContext:
    # Stages only touch ctx.anthropic / ctx.model here; mcp and retriever unused.
    return AgentContext(mcp=None, retriever=None, anthropic=anthropic, model="test-model")


async def test_returns_validated_output_and_caches_system(fake_anthropic):
    intent = StructuredIntent(summary="finance -> salesforce", applications=["salesforce"])
    ctx = _ctx(fake_anthropic([intent]))

    result = await complete_structured(
        ctx, system="SYS", user="finance needs salesforce", schema=StructuredIntent
    )

    assert result is intent
    # The stage's static instructions go in a cache-controlled system block.
    call = ctx.anthropic.messages.calls[0]
    assert call["output_format"] is StructuredIntent
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert call["system"][0]["text"] == "SYS"


async def test_returns_none_on_refusal(fake_anthropic):
    refusal = fake_anthropic.ParsedMessage(parsed_output=None, stop_reason="refusal")
    ctx = _ctx(fake_anthropic([refusal]))

    result = await complete_structured(ctx, system="SYS", user="...", schema=StructuredIntent)

    assert result is None
