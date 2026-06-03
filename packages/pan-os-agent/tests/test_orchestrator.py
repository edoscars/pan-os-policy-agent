"""Tests for the run_agent loop, using injected fake stages.

Tests the loop's contract — run in order, thread state through, stop on halt —
not the real stages (those are tested individually).
"""

from pan_os_agent.orchestrator import run_agent
from pan_os_agent.state import PolicyDraftState


def _stage(name: str):
    """Build a fake stage that records that it ran in the trace."""

    async def stage(state: PolicyDraftState, ctx) -> PolicyDraftState:
        return state.advance(stage=name, summary=f"{name} ran")

    return stage


def _halting_stage(name: str):
    async def stage(state: PolicyDraftState, ctx) -> PolicyDraftState:
        return state.halt(stage=name, reason="stop here")

    return stage


async def test_run_agent_runs_stages_in_order():
    state = PolicyDraftState(intent_text="x")

    result = await run_agent(state, ctx=None, stages=[_stage("a"), _stage("b")])

    assert [t.stage for t in result.trace] == ["a", "b"]


async def test_run_agent_stops_at_first_halt():
    state = PolicyDraftState(intent_text="x")

    result = await run_agent(
        state, ctx=None, stages=[_stage("a"), _halting_stage("b"), _stage("c")]
    )

    assert result.halted is True
    # "c" never ran
    assert [t.stage for t in result.trace] == ["a", "b"]
