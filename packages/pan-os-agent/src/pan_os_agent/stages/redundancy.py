"""Stage 3 — redundancy check.

Ask whether the current Security policy already satisfies the intent. If an
existing rule covers it, there's nothing to propose, so the gauntlet halts with
that rule named. Otherwise it advances to the proposal stage.
"""

import json

from pan_os_agent.context import AgentContext
from pan_os_agent.llm import complete_structured
from pan_os_agent.models import RedundancyReport, StructuredIntent
from pan_os_agent.state import PolicyDraftState

SYSTEM = """You determine whether an existing PAN-OS Security rule already \
satisfies a proposed access intent.

You are given the structured intent and the current Security rulebase in \
evaluation order (top-down, first match wins).

A rule satisfies the intent only if, for traffic matching the intent, that rule \
already handles it as the intent requires: its action matches the intent's \
action, and each of its match fields (zones, source, destination, user, \
application, service) is equal to or broader than the intent's ("any" is \
broader than any specific value). A disabled rule satisfies nothing, and a \
satisfying allow rule must not be preceded by an earlier rule that would block \
the same traffic.

Set redundant=true only when such a rule exists — name it in matching_rule and \
justify in reasoning. Otherwise set redundant=false and describe the gap in \
reasoning."""


def _format_user(intent: StructuredIntent, rules: list[dict]) -> str:
    return (
        f"INTENT:\n{intent.model_dump_json(indent=2)}\n\n"
        f"CURRENT SECURITY RULEBASE (evaluation order):\n{json.dumps(rules, indent=2)}"
    )


async def check_redundancy(state: PolicyDraftState, ctx: AgentContext) -> PolicyDraftState:
    intent = state.structured_intent

    rules = (await ctx.mcp.call_tool("list_security_rules"))["result"]
    user = _format_user(intent, rules)

    report = await complete_structured(
        ctx, system=SYSTEM, user=user, schema=RedundancyReport
    )
    if report is None:
        return state.halt(stage="redundancy", reason="model refused the redundancy check")

    if report.redundant:
        return state.halt(
            stage="redundancy",
            reason=f"intent already satisfied by rule '{report.matching_rule}'",
            redundancy=report,
        )

    return state.advance(
        stage="redundancy", summary="no existing rule satisfies the intent", redundancy=report
    )
