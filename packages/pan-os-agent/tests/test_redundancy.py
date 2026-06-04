"""Tests for stage 3 — redundancy check."""

from pan_os_agent.context import AgentContext
from pan_os_agent.models import RedundancyReport, StructuredIntent
from pan_os_agent.stages.redundancy import check_redundancy
from pan_os_agent.state import PolicyDraftState


def _ctx(mcp, anthropic):
    return AgentContext(mcp=mcp, retriever=None, anthropic=anthropic, model="test-model")


def _rules(*names):
    return {"list_security_rules": {"result": [{"name": n} for n in names]}}


def _state():
    intent = StructuredIntent(summary="finance -> salesforce", source_user="finance")
    return PolicyDraftState(intent_text="finance needs salesforce", structured_intent=intent)


async def test_redundant_halts_naming_the_rule(fake_mcp, fake_anthropic):
    report = RedundancyReport(redundant=True, matching_rule="allow-finance-saas",
                              reasoning="broader allow already covers it")
    ctx = _ctx(fake_mcp(_rules("allow-finance-saas")), fake_anthropic([report]))

    result = await check_redundancy(_state(), ctx)

    assert result.halted is True
    assert "allow-finance-saas" in result.halt_reason
    assert result.redundancy is report
    # The rulebase was threaded to Claude.
    assert "allow-finance-saas" in ctx.anthropic.messages.calls[0]["messages"][0]["content"]


async def test_not_redundant_advances(fake_mcp, fake_anthropic):
    report = RedundancyReport(redundant=False, reasoning="no rule allows finance->salesforce")
    ctx = _ctx(fake_mcp(_rules("deny-all")), fake_anthropic([report]))

    result = await check_redundancy(_state(), ctx)

    assert result.halted is False
    assert result.redundancy is report
    assert result.trace[-1].stage == "redundancy"


async def test_refusal_halts(fake_mcp, fake_anthropic):
    refusal = fake_anthropic.ParsedMessage(parsed_output=None, stop_reason="refusal")
    ctx = _ctx(fake_mcp(_rules()), fake_anthropic([refusal]))

    result = await check_redundancy(_state(), ctx)

    assert result.halted is True
    assert "refused" in result.halt_reason
