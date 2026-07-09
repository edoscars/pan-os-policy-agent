"""Shared user-message formatting for stages that reason over the rulebase.

The redundancy and proposal stages send Claude the same shape of context — the
structured intent plus the current Security rulebase in evaluation order — so
that formatting lives here once instead of being duplicated in each stage.
"""

import json

from pan_os_agent.models import StructuredIntent


def format_intent_and_rulebase(intent: StructuredIntent, rules: list[dict]) -> str:
    return (
        f"INTENT:\n{intent.model_dump_json(indent=2)}\n\n"
        f"CURRENT SECURITY RULEBASE (evaluation order):\n{json.dumps(rules, indent=2)}"
    )
