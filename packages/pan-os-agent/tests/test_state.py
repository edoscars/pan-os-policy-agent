"""Tests for PolicyDraftState's append-only semantics."""

from pan_os_agent.models import StructuredIntent
from pan_os_agent.state import PolicyDraftState


def test_advance_appends_trace_and_applies_updates_without_mutating_original():
    original = PolicyDraftState(intent_text="finance needs salesforce")

    advanced = original.advance(
        stage="intent",
        summary="parsed finance -> salesforce",
        structured_intent=StructuredIntent(summary="finance -> salesforce"),
    )

    # original is untouched (frozen, append-only)
    assert original.structured_intent is None
    assert original.trace == []

    # advanced carries the update plus a trace breadcrumb
    assert advanced.structured_intent.summary == "finance -> salesforce"
    assert [t.stage for t in advanced.trace] == ["intent"]
    assert advanced.halted is False


def test_halt_sets_flag_reason_and_traces():
    state = PolicyDraftState(intent_text="gibberish").halt(
        stage="intent", reason="intent is incoherent"
    )

    assert state.halted is True
    assert state.halt_reason == "intent is incoherent"
    assert state.trace[-1].summary == "halted: intent is incoherent"


def test_state_is_json_serializable_round_trip():
    state = PolicyDraftState(intent_text="x").advance(
        stage="intent", summary="ok", structured_intent=StructuredIntent()
    )

    restored = PolicyDraftState.model_validate_json(state.model_dump_json())

    assert restored == state
