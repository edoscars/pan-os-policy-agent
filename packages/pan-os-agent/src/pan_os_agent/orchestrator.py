"""The hand-rolled state machine that runs the four-stage gauntlet.

Deliberately not LangGraph/LangChain: the loop is the whole thing. Stages are
async (state, ctx) -> state functions; the loop runs them in order and stops
early if a stage halts. STAGES is populated as the stages are built.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

from pan_os_agent.context import AgentContext
from pan_os_agent.llm import GuardrailBlocked
from pan_os_agent.stages.intent import validate_intent
from pan_os_agent.stages.prerequisite import check_prerequisites
from pan_os_agent.stages.proposal import propose_rule
from pan_os_agent.stages.redundancy import check_redundancy
from pan_os_agent.state import PolicyDraftState

Stage = Callable[[PolicyDraftState, AgentContext], Awaitable[PolicyDraftState]]

# The four-stage gauntlet, in execution order.
STAGES: list[Stage] = [
    validate_intent,
    check_prerequisites,
    check_redundancy,
    propose_rule,
]

# Display labels for the live UI, keyed by the stage's trace name.
STAGE_LABELS: dict[str, str] = {
    "intent": "Intent validation",
    "prerequisite": "Prerequisite check",
    "redundancy": "Redundancy check",
    "proposal": "Proposal + shadowing",
    "security": "Prisma AIRS guardrail",
}


async def run_agent_streamed(
    state: PolicyDraftState,
    ctx: AgentContext,
    stages: list[Stage] | None = None,
) -> AsyncIterator[PolicyDraftState]:
    """Run the gauntlet, yielding the state after each stage.

    The core loop lives here so the UI can render progress stage-by-stage; the
    non-streaming `run_agent` just drains this. A guardrail denial at the gateway
    (Prisma AIRS) surfaces as GuardrailBlocked on the triggering call and is
    turned into a clean security halt — the model output is never produced, so
    the agent stops at the door. Stops after the first halting stage.
    """
    for stage in stages if stages is not None else STAGES:
        try:
            state = await stage(state, ctx)
        except GuardrailBlocked as blocked:
            reason = "Prisma AIRS (via Portkey) denied the request"
            if blocked.detail:
                reason += f": {blocked.detail}"
            yield state.halt(stage="security", reason=reason)
            return
        yield state
        if state.halted:
            return


async def run_agent(
    state: PolicyDraftState,
    ctx: AgentContext,
    stages: list[Stage] | None = None,
) -> PolicyDraftState:
    """Run the gauntlet to completion and return the final state.

    Thin consumer of run_agent_streamed; `stages` is injectable for tests.
    """
    async for state in run_agent_streamed(state, ctx, stages):
        pass
    return state
