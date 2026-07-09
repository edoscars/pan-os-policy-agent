"""Tests for the run_agent loop, using injected fake stages.

Tests the loop's contract — run in order, thread state through, stop on halt —
not the real stages (those are tested individually).
"""

from pan_os_agent.orchestrator import run_agent, run_agent_streamed
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


async def test_run_agent_streamed_yields_after_each_stage():
    state = PolicyDraftState(intent_text="x")

    seen = [
        s async for s in run_agent_streamed(
            state, ctx=None, stages=[_stage("a"), _stage("b")]
        )
    ]

    # One yield per stage, each carrying the cumulative trace.
    assert [s.trace[-1].stage for s in seen] == ["a", "b"]
    assert [len(s.trace) for s in seen] == [1, 2]


async def test_run_agent_streamed_stops_after_halt():
    state = PolicyDraftState(intent_text="x")

    seen = [
        s async for s in run_agent_streamed(
            state, ctx=None, stages=[_stage("a"), _halting_stage("b"), _stage("c")]
        )
    ]

    assert seen[-1].halted is True
    assert [s.trace[-1].stage for s in seen] == ["a", "b"]
