"""Tests for stage 4 — proposal + shadowing."""

from pan_os_agent.context import AgentContext
from pan_os_agent.models import Proposal, ProposedRule, ShadowAssessment, StructuredIntent
from pan_os_agent.stages.proposal import propose_rule
from pan_os_agent.state import PolicyDraftState


def _ctx(mcp, anthropic):
    return AgentContext(mcp=mcp, retriever=None, anthropic=anthropic, model="test-model")


def _rules(*names):
    return {"list_security_rules": {"result": [{"name": n} for n in names]}}


def _state():
    intent = StructuredIntent(summary="block facebook from trust", source_zones=["trust"],
                              applications=["facebook"], action="deny")
    return PolicyDraftState(intent_text="block facebook", structured_intent=intent)


async def test_proposes_rule_and_advances(fake_mcp, fake_anthropic):
    proposal = Proposal(
        rule=ProposedRule(name="deny-facebook-trust", from_zones=["trust"],
                          applications=["facebook"], action="deny"),
        shadow=ShadowAssessment(shadowed=False),
    )
    ctx = _ctx(fake_mcp(_rules("deny-all")), fake_anthropic([proposal]))

    result = await propose_rule(_state(), ctx)

    assert result.halted is False
    assert result.proposal.rule.name == "deny-facebook-trust"
    assert result.trace[-1].summary == "proposed rule 'deny-facebook-trust'"


async def test_shadowed_proposal_notes_shadowing_rule_in_summary(fake_mcp, fake_anthropic):
    proposal = Proposal(
        rule=ProposedRule(name="deny-facebook-trust", action="deny"),
        shadow=ShadowAssessment(shadowed=True, shadowing_rule="Allow all but alert",
                                reasoning="earlier any/any allow intercepts this traffic"),
    )
    ctx = _ctx(fake_mcp(_rules("Allow all but alert")), fake_anthropic([proposal]))

    result = await propose_rule(_state(), ctx)

    assert result.halted is False
    assert result.proposal.shadow.shadowed is True
    assert "shadowed by 'Allow all but alert'" in result.trace[-1].summary


async def test_refusal_halts(fake_mcp, fake_anthropic):
    refusal = fake_anthropic.ParsedMessage(parsed_output=None, stop_reason="refusal")
    ctx = _ctx(fake_mcp(_rules()), fake_anthropic([refusal]))

    result = await propose_rule(_state(), ctx)

    assert result.halted is True
    assert "refused" in result.halt_reason
