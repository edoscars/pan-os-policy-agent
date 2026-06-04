"""Tests for the driver's pure helpers."""

from pan_os_agent.driver import load_intents, render_outcome
from pan_os_agent.models import Proposal, ProposedRule, ShadowAssessment, StructuredIntent
from pan_os_agent.state import PolicyDraftState


def test_load_intents_skips_blanks_and_comments(tmp_path):
    f = tmp_path / "intents.txt"
    f.write_text(
        "# a comment\n\nfinance needs salesforce\n  block tiktok  \n\n# trailing\n",
        encoding="utf-8",
    )

    assert load_intents(f) == ["finance needs salesforce", "block tiktok"]


def test_render_outcome_shows_halt_reason():
    state = PolicyDraftState(intent_text="gibberish").halt(
        stage="intent", reason="not an access request"
    )

    rendered = render_outcome(state)

    assert "HALTED: not an access request" in rendered
    assert "PROPOSED RULE" not in rendered


def test_render_outcome_shows_proposed_rule_with_caveats():
    proposal = Proposal(
        rule=ProposedRule(name="deny-facebook-trust", from_zones=["trust"],
                          applications=["facebook"], action="deny"),
        shadow=ShadowAssessment(shadowed=True, shadowing_rule="Allow all but alert"),
    )
    state = (
        PolicyDraftState(intent_text="block facebook",
                         structured_intent=StructuredIntent(summary="x"))
        .advance(stage="proposal", summary="proposed", proposal=proposal)
    )

    rendered = render_outcome(state)

    assert "PROPOSED RULE (pending approval" in rendered
    assert "deny-facebook-trust" in rendered
    assert "shadowed by: Allow all but alert" in rendered
