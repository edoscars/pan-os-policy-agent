"""Tests for stage 2 — prerequisite check."""

from pan_os_agent.context import AgentContext
from pan_os_agent.models import (
    PrerequisiteFinding,
    PrerequisiteReport,
    StructuredIntent,
)
from pan_os_agent.stages.prerequisite import check_prerequisites
from pan_os_agent.state import PolicyDraftState
from pan_os_rag.chunk import Chunk


def _inventory(zones=(), address_objects=(), address_groups=(), services=()):
    """Shape canned tool results like the real list_* tools ({"result": [...]})."""
    def wrap(names):
        return {"result": [{"name": n} for n in names]}
    return {
        "list_zones": wrap(zones),
        "list_address_objects": wrap(address_objects),
        "list_address_groups": wrap(address_groups),
        "list_services": wrap(services),
    }


def _chunk(text):
    return Chunk(text=text, source_url="https://docs/x", page_title="User-ID",
                heading_path=["User-ID", "Enable"], position=0)


async def test_gathers_inventory_retrieves_docs_and_attaches_report(fake_mcp, fake_anthropic):
    report = PrerequisiteReport(
        findings=[
            PrerequisiteFinding(requirement="zone 'trust'", satisfied=True),
            PrerequisiteFinding(requirement="User-ID enabled", satisfied=False,
                                detail="enable User-ID on the source zone"),
        ],
        all_satisfied=False,
    )
    retrieved = []

    def retriever(query, k):
        retrieved.append((query, k))
        return [_chunk("To match users, enable User-ID on the zone.")]

    ctx = AgentContext(
        mcp=fake_mcp(_inventory(zones=["trust", "untrust"])),
        retriever=retriever,
        anthropic=fake_anthropic([report]),
        model="test-model",
    )
    intent = StructuredIntent(summary="finance -> salesforce", source_user="finance")
    state = PolicyDraftState(intent_text="finance needs salesforce", structured_intent=intent)

    result = await check_prerequisites(state, ctx)

    # All four inventory tools were queried.
    assert {name for name, _ in ctx.mcp.calls} == {
        "list_zones", "list_address_objects", "list_address_groups", "list_services",
    }
    # Retrieval used the intent summary.
    assert retrieved == [("finance -> salesforce", 5)]
    # Report attached, not halted, summary counts satisfied findings.
    assert result.halted is False
    assert result.prerequisites is report
    assert result.trace[-1].summary == "1/2 prerequisites satisfied"
    # The prompt threaded inventory + docs to Claude.
    sent = ctx.anthropic.messages.calls[0]["messages"][0]["content"]
    assert "trust" in sent and "User-ID" in sent


async def test_refusal_halts(fake_mcp, fake_anthropic):
    refusal = fake_anthropic.ParsedMessage(parsed_output=None, stop_reason="refusal")
    ctx = AgentContext(
        mcp=fake_mcp(_inventory()),
        retriever=lambda q, k: [],
        anthropic=fake_anthropic([refusal]),
        model="test-model",
    )
    intent = StructuredIntent(summary="x")
    state = PolicyDraftState(intent_text="x", structured_intent=intent)

    result = await check_prerequisites(state, ctx)

    assert result.halted is True
    assert "refused" in result.halt_reason
