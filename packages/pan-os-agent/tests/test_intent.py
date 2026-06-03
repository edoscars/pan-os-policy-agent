"""Tests for stage 1 — intent validation."""

from pan_os_agent.context import AgentContext
from pan_os_agent.models import IntentAssessment, StructuredIntent
from pan_os_agent.stages.intent import validate_intent
from pan_os_agent.state import PolicyDraftState


def _ctx(anthropic) -> AgentContext:
    return AgentContext(mcp=None, retriever=None, anthropic=anthropic, model="test-model")


async def test_coherent_intent_advances_and_attaches_structured_intent(fake_anthropic):
    intent = StructuredIntent(summary="finance -> salesforce", source_user="finance",
                              applications=["salesforce"])
    ctx = _ctx(fake_anthropic([IntentAssessment(coherent=True, intent=intent)]))
    state = PolicyDraftState(intent_text="finance group needs Salesforce")

    result = await validate_intent(state, ctx)

    assert result.halted is False
    assert result.structured_intent.applications == ["salesforce"]
    assert result.trace[-1].stage == "intent"
    # The raw intent text is what the stage sent to Claude.
    assert ctx.anthropic.messages.calls[0]["messages"][0]["content"] == \
        "finance group needs Salesforce"


async def test_incoherent_intent_halts_with_issue(fake_anthropic):
    assessment = IntentAssessment(coherent=False, issue="not an access request",
                                  intent=StructuredIntent())
    ctx = _ctx(fake_anthropic([assessment]))
    state = PolicyDraftState(intent_text="what's the weather")

    result = await validate_intent(state, ctx)

    assert result.halted is True
    assert result.halt_reason == "not an access request"


async def test_refusal_halts(fake_anthropic):
    refusal = fake_anthropic.ParsedMessage(parsed_output=None, stop_reason="refusal")
    ctx = _ctx(fake_anthropic([refusal]))
    state = PolicyDraftState(intent_text="...")

    result = await validate_intent(state, ctx)

    assert result.halted is True
    assert "refused" in result.halt_reason
