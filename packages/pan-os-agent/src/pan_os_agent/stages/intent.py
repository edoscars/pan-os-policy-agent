"""Stage 1 — intent validation.

Parse the natural-language policy request into structured PAN-OS security-rule
terms and judge whether it's a coherent access-control intent at all. Halt the
gauntlet here if it isn't — the later stages assume a usable intent.
"""

from pan_os_agent.context import AgentContext
from pan_os_agent.llm import complete_structured
from pan_os_agent.models import IntentAssessment
from pan_os_agent.state import PolicyDraftState

SYSTEM = """You parse a natural-language firewall policy request into structured \
PAN-OS security-rule terms.

A coherent request expresses who (a source: user/group, zone, or address) should \
be allowed or denied access to what (a destination: application/service, zone, or \
address). Set coherent=false only when the text is not an access-control request \
at all — gibberish, off-topic, or missing both a subject and an object. When \
coherent=false, set `issue` to a one-sentence explanation.

Extract only what is explicitly stated; leave every other field empty. Do not \
invent zones, addresses, or services. Map obvious application names to their \
PAN-OS App-ID (e.g. "Salesforce" -> "salesforce"). Default action to "allow" \
unless the request is clearly a denial. `summary` is a one-line restatement of \
the access being requested."""


async def validate_intent(state: PolicyDraftState, ctx: AgentContext) -> PolicyDraftState:
    assessment = await complete_structured(
        ctx, system=SYSTEM, user=state.intent_text, schema=IntentAssessment
    )

    if assessment is None:
        return state.halt(stage="intent", reason="model refused to parse the intent")

    if not assessment.coherent:
        return state.halt(
            stage="intent",
            reason=assessment.issue or "intent is not a coherent access request",
            structured_intent=assessment.intent,
        )

    return state.advance(
        stage="intent",
        summary=assessment.intent.summary,
        structured_intent=assessment.intent,
    )
