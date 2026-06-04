"""Stage 2 — prerequisite check.

Verify the intent's prerequisites: do the named zones/addresses/services exist
on the firewall (MCP inventory), and are the implied configuration prerequisites
(User-ID, decryption, ...) in place (grounded in retrieved docs)? This stage
flags what's missing and carries it forward — it does not halt, because v1
produces a proposal-with-caveats rather than gating on prerequisites.
"""

import asyncio

from pan_os_agent.context import AgentContext
from pan_os_agent.llm import complete_structured
from pan_os_agent.models import PrerequisiteReport, StructuredIntent
from pan_os_agent.state import PolicyDraftState
from pan_os_rag.chunk import Chunk

# Inventory category -> MCP tool that lists it.
INVENTORY_TOOLS = {
    "zones": "list_zones",
    "address_objects": "list_address_objects",
    "address_groups": "list_address_groups",
    "services": "list_services",
}

RETRIEVAL_K = 5

SYSTEM = """You verify the prerequisites for a proposed PAN-OS security policy.

You are given: (1) a structured policy intent, (2) an inventory of objects that \
currently exist on the firewall, and (3) reference documentation excerpts.

Produce a prerequisite report with one finding per requirement:
- For every zone, address (object or group), and service the intent names by a \
specific identifier, add a finding checking whether that exact name appears in \
the firewall inventory (satisfied=true if present, false if absent). Predefined \
applications and the implicit "any" / "application-default" values are not \
objects — do not flag them.
- Using the reference docs, add findings for configuration prerequisites the \
intent implies (e.g. matching a user/group requires User-ID enabled). Mark these \
satisfied only when the intent or inventory shows they are met; otherwise \
satisfied=false with a one-sentence detail of what is required.

Set all_satisfied=true only if every finding is satisfied. Ground configuration \
findings in the provided docs; do not invent requirements they do not support."""


async def _gather_inventory(mcp) -> dict[str, list[str]]:
    """Concurrently list each inventory category, returning category -> names."""
    results = await asyncio.gather(
        *(mcp.call_tool(tool) for tool in INVENTORY_TOOLS.values())
    )
    return {
        category: [item["name"] for item in result["result"]]
        for category, result in zip(INVENTORY_TOOLS, results)
    }


def _format_docs(chunks: list[Chunk]) -> str:
    if not chunks:
        return "(no documentation retrieved)"
    blocks = []
    for i, c in enumerate(chunks, 1):
        heading = " > ".join(c.heading_path) if c.heading_path else c.page_title
        blocks.append(f"[doc {i}] {heading}\n{c.text}")
    return "\n\n".join(blocks)


def _format_user(intent: StructuredIntent, inventory: dict[str, list[str]],
                 chunks: list[Chunk]) -> str:
    inventory_lines = "\n".join(
        f"{category}: {names or '(none)'}" for category, names in inventory.items()
    )
    return (
        f"INTENT:\n{intent.model_dump_json(indent=2)}\n\n"
        f"FIREWALL INVENTORY:\n{inventory_lines}\n\n"
        f"REFERENCE DOCS:\n{_format_docs(chunks)}"
    )


async def check_prerequisites(state: PolicyDraftState, ctx: AgentContext) -> PolicyDraftState:
    intent = state.structured_intent

    inventory = await _gather_inventory(ctx.mcp)
    chunks = ctx.retriever(intent.summary, RETRIEVAL_K)
    user = _format_user(intent, inventory, chunks)

    report = await complete_structured(
        ctx, system=SYSTEM, user=user, schema=PrerequisiteReport
    )
    if report is None:
        return state.halt(stage="prerequisite", reason="model refused the prerequisite check")

    # Record which docs grounded this check (Claude doesn't see chunk_ids).
    report = report.model_copy(update={"retrieved_doc_ids": [c.chunk_id for c in chunks]})

    satisfied = sum(f.satisfied for f in report.findings)
    summary = f"{satisfied}/{len(report.findings)} prerequisites satisfied"
    return state.advance(stage="prerequisite", summary=summary, prerequisites=report)
