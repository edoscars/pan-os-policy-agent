"""Single-shot driver helpers: load intents, run them, render the outcome.

The pure pieces live here (importable, testable); scripts/run_agent.py is the
thin CLI wrapper that builds the real collaborators and owns the McpClient
lifecycle.
"""

from pathlib import Path

from pan_os_agent.context import AgentContext
from pan_os_agent.orchestrator import run_agent
from pan_os_agent.state import PolicyDraftState


def load_intents(path: Path) -> list[str]:
    """Read one intent per line from a fixtures file; skip blanks and # comments."""
    intents = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            intents.append(line)
    return intents


async def run_intents(
    intents: list[str], ctx: AgentContext, stages=None
) -> list[PolicyDraftState]:
    """Run the gauntlet for each intent, reusing one context (one MCP server).

    `stages` is forwarded to run_agent (defaults to the core gauntlet); kept
    injectable so callers and tests can supply a custom stage list.
    """
    results = []
    for text in intents:
        results.append(await run_agent(PolicyDraftState(intent_text=text), ctx, stages))
    return results


def render_outcome(state: PolicyDraftState) -> str:
    """Render a human-readable outcome for the fake approval gate.

    A halted run shows where and why it stopped. A completed run shows the
    proposed rule with its prerequisite and shadowing caveats — explicitly
    pending approval, since v1 never commits.
    """
    lines = [f"INTENT: {state.intent_text}"]
    lines += [f"  trace: {' -> '.join(t.stage for t in state.trace)}"]

    if state.halted:
        lines.append(f"  HALTED: {state.halt_reason}")
        return "\n".join(lines)

    rule = state.proposal.rule
    lines.append("  PROPOSED RULE (pending approval - v1 never commits):")
    lines += [
        f"    name:         {rule.name}",
        f"    from -> to:   {rule.from_zones} -> {rule.to_zones}",
        f"    source/dest:  {rule.sources} -> {rule.destinations}",
        f"    user:         {rule.source_users}",
        f"    application:  {rule.applications}",
        f"    service:      {rule.services}",
        f"    action:       {rule.action}",
    ]

    if state.prerequisites and not state.prerequisites.all_satisfied:
        unmet = [f.requirement for f in state.prerequisites.findings if not f.satisfied]
        lines.append(f"    ! prerequisites unmet: {unmet}")
    if state.proposal.shadow.shadowed:
        lines.append(f"    ! shadowed by: {state.proposal.shadow.shadowing_rule}")

    return "\n".join(lines)
