"""The hand-rolled state machine that runs the four-stage gauntlet.

Deliberately not LangGraph/LangChain: the loop is the whole thing. Stages are
async (state, ctx) -> state functions; the loop runs them in order and stops
early if a stage halts. STAGES is populated as the stages are built.
"""

from collections.abc import Awaitable, Callable

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


async def run_agent(
    state: PolicyDraftState,
    ctx: AgentContext,
    stages: list[Stage] | None = None,
) -> PolicyDraftState:
    """Run the gauntlet: each stage transforms the state until one halts.

    `stages` is injectable so the loop can be tested with fakes; it defaults
    to the real STAGES. A guardrail denial at the gateway (Prisma AIRS, in the
    secured product) surfaces as GuardrailBlocked on the call that triggered it,
    and is turned into a clean security halt — the model output for that call is
    never produced, so the agent stops at the door.
    """
    for stage in stages if stages is not None else STAGES:
        try:
            state = await stage(state, ctx)
        except GuardrailBlocked as blocked:
            reason = "Prisma AIRS (via Portkey) denied the request"
            if blocked.detail:
                reason += f": {blocked.detail}"
            return state.halt(stage="security", reason=reason)
        if state.halted:
            break
    return state
