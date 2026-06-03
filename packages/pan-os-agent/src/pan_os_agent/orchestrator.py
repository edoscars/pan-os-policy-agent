"""The hand-rolled state machine that runs the four-stage gauntlet.

Deliberately not LangGraph/LangChain: the loop is the whole thing. Stages are
async (state, ctx) -> state functions; the loop runs them in order and stops
early if a stage halts. STAGES is populated as the stages are built.
"""

from collections.abc import Awaitable, Callable

from pan_os_agent.context import AgentContext
from pan_os_agent.state import PolicyDraftState

Stage = Callable[[PolicyDraftState, AgentContext], Awaitable[PolicyDraftState]]

# Filled in as stages land (Block 4), in execution order.
STAGES: list[Stage] = []


async def run_agent(
    state: PolicyDraftState,
    ctx: AgentContext,
    stages: list[Stage] | None = None,
) -> PolicyDraftState:
    """Run the gauntlet: each stage transforms the state until one halts.

    `stages` is injectable so the loop can be tested with fakes; it defaults
    to the real STAGES.
    """
    for stage in stages if stages is not None else STAGES:
        state = await stage(state, ctx)
        if state.halted:
            break
    return state
