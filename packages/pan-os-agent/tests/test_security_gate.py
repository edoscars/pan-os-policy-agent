"""Tests for the secured-only Prisma AIRS gate stage.

Uses a fake AIRS scanner injected via AgentContext.airs, so these run without
the aisecurity SDK installed (the concrete scanner is the only thing that
imports it).
"""

from pan_os_agent.context import AgentContext
from pan_os_agent.models import Proposal, ProposedRule, ShadowAssessment, StructuredIntent
from pan_os_agent.orchestrator import STAGES
from pan_os_agent.security.gate import SECURED_STAGES, security_gate
from pan_os_agent.security.types import AirsVerdict
from pan_os_agent.state import PolicyDraftState


class FakeAirs:
    def __init__(self, verdict: AirsVerdict) -> None:
        self._verdict = verdict
        self.calls: list[tuple[str, str]] = []

    async def scan(self, prompt: str, response: str) -> AirsVerdict:
        self.calls.append((prompt, response))
        return self._verdict


def _ctx(airs) -> AgentContext:
    return AgentContext(mcp=None, retriever=None, anthropic=None, airs=airs)


def _proposal_state() -> PolicyDraftState:
    proposal = Proposal(
        rule=ProposedRule(name="allow-finance-salesforce", action="allow"),
        shadow=ShadowAssessment(shadowed=False),
    )
    return (
        PolicyDraftState(intent_text="let finance reach salesforce",
                         structured_intent=StructuredIntent(summary="x"))
        .advance(stage="proposal", summary="r", proposal=proposal)
    )


async def test_blocked_verdict_halts():
    airs = FakeAirs(AirsVerdict(blocked=True, category="malicious"))

    result = await security_gate(_proposal_state(), _ctx(airs))

    assert result.halted is True
    assert "Prisma AIRS blocked" in result.halt_reason
    assert "malicious" in result.halt_reason


async def test_clean_verdict_advances():
    airs = FakeAirs(AirsVerdict(blocked=False, category="benign"))

    result = await security_gate(_proposal_state(), _ctx(airs))

    assert result.halted is False
    assert result.trace[-1].stage == "security"


async def test_scans_both_intent_and_proposed_rule():
    airs = FakeAirs(AirsVerdict(blocked=False))

    await security_gate(_proposal_state(), _ctx(airs))

    prompt, response = airs.calls[0]
    assert prompt == "let finance reach salesforce"           # the raw user input
    assert '"name":"allow-finance-salesforce"' in response    # the proposed action


def test_secured_stages_is_core_plus_gate():
    assert SECURED_STAGES == [*STAGES, security_gate]
