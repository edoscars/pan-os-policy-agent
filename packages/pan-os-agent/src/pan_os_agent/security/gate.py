"""Secured-only stage — the Prisma AIRS action gate.

Runs after the proposal: it scans the original intent (where a prompt-injection
or malicious request lives) together with the agent's proposed rule (the action
AIRS guards), and halts before the approval gate if AIRS blocks. Appended to the
core gauntlet only in the secured product, so the unsecured product is unchanged.
"""

from pan_os_agent.context import AgentContext
from pan_os_agent.orchestrator import STAGES
from pan_os_agent.state import PolicyDraftState


async def security_gate(state: PolicyDraftState, ctx: AgentContext) -> PolicyDraftState:
    rule_json = state.proposal.rule.model_dump_json() if state.proposal else ""
    verdict = await ctx.airs.scan(prompt=state.intent_text, response=rule_json)

    if verdict.blocked:
        return state.halt(
            stage="security",
            reason=f"Prisma AIRS blocked the action (category: {verdict.category})",
        )
    return state.advance(
        stage="security",
        summary=f"Prisma AIRS cleared the action ({verdict.category or 'benign'})",
    )


# The secured gauntlet: the four core stages, then the AIRS action gate.
SECURED_STAGES = [*STAGES, security_gate]
