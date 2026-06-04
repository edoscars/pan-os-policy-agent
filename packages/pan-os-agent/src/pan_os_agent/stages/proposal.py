"""Stage 4 — proposal + shadowing.

Generate the proposed Security rule for the intent and check whether an earlier,
broader rule would shadow it (intercept its traffic so it never takes effect).
This is the gauntlet's terminal output; shadowing is surfaced as a warning for
the approval gate, not a rejection, so the stage advances with the proposal.
"""

import json

from pan_os_agent.context import AgentContext
from pan_os_agent.llm import complete_structured
from pan_os_agent.models import Proposal, StructuredIntent
from pan_os_agent.state import PolicyDraftState

SYSTEM = """You propose a PAN-OS Security rule for an intent and check whether it \
would be shadowed.

You are given the structured intent and the current Security rulebase in \
evaluation order (top-down, first match wins).

First, produce a complete proposed rule implementing the intent. Fill fields the \
intent leaves unspecified with safe PAN-OS defaults: zones the intent implies or \
"any" if none are stated, source/destination "any" unless specified, source_user \
"any" unless a user or group is named, application from the intent (or "any"), \
service "application-default" unless a specific service is named, and the \
intent's action. Give it a short lowercase hyphenated name and a one-line \
description.

Then assess shadowing: assume the proposed rule is placed at the bottom of the \
rulebase, just above the default rule. It is shadowed if an earlier ENABLED rule \
already matches all of the proposed rule's traffic (its match fields are equal to \
or broader than the proposed rule's), so the proposed rule would never be \
evaluated. Set shadowed=true and name it in shadowing_rule with an explanation; \
otherwise shadowed=false. The proposed rule must be valid even when shadowed — \
shadowing is a warning, not a rejection."""


def _format_user(intent: StructuredIntent, rules: list[dict]) -> str:
    return (
        f"INTENT:\n{intent.model_dump_json(indent=2)}\n\n"
        f"CURRENT SECURITY RULEBASE (evaluation order):\n{json.dumps(rules, indent=2)}"
    )


async def propose_rule(state: PolicyDraftState, ctx: AgentContext) -> PolicyDraftState:
    intent = state.structured_intent

    rules = (await ctx.mcp.call_tool("list_security_rules"))["result"]
    user = _format_user(intent, rules)

    proposal = await complete_structured(ctx, system=SYSTEM, user=user, schema=Proposal)
    if proposal is None:
        return state.halt(stage="proposal", reason="model refused to generate a proposal")

    summary = f"proposed rule '{proposal.rule.name}'"
    if proposal.shadow.shadowed:
        summary += f" (shadowed by '{proposal.shadow.shadowing_rule}')"
    return state.advance(stage="proposal", summary=summary, proposal=proposal)
