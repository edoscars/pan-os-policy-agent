"""Tests for the grounding eval scorer."""

from pan_os_agent.grounding import EvalCase, case_passed, load_cases, outcome_of, score_case
from pan_os_agent.models import (
    PrerequisiteFinding,
    PrerequisiteReport,
    Proposal,
    ProposedRule,
    ShadowAssessment,
    StructuredIntent,
)
from pan_os_agent.state import PolicyDraftState


def _halted_at(stage, reason="x"):
    return PolicyDraftState(intent_text="x").halt(stage=stage, reason=reason)


def _proposal_state(rule, *, shadowed=False, unmet=()):
    prereqs = PrerequisiteReport(
        findings=[PrerequisiteFinding(requirement=r, satisfied=False) for r in unmet],
        all_satisfied=not unmet,
    )
    proposal = Proposal(rule=rule, shadow=ShadowAssessment(shadowed=shadowed))
    return (
        PolicyDraftState(intent_text="x", structured_intent=StructuredIntent(summary="x"))
        .advance(stage="prerequisite", summary="p", prerequisites=prereqs)
        .advance(stage="proposal", summary="r", proposal=proposal)
    )


def test_outcome_of_classifies_halt_and_proposal():
    assert outcome_of(_halted_at("intent")) == "halt@intent"
    assert outcome_of(_halted_at("redundancy")) == "halt@redundancy"
    assert outcome_of(_proposal_state(ProposedRule(name="r"))) == "proposal"


def test_score_case_all_pass():
    case = EvalCase(intent="block tiktok", expect_outcome="proposal", expect_action="deny",
                    expect_applications=["tiktok"], expect_shadowed=True)
    state = _proposal_state(
        ProposedRule(name="deny-tiktok", applications=["tiktok"], action="deny"),
        shadowed=True,
    )

    checks = score_case(case, state)

    assert checks == {"outcome": True, "action": True, "applications": True, "shadowed": True}
    assert case_passed(checks)


def test_score_case_flags_wrong_action_and_missing():
    case = EvalCase(intent="dmz to db", expect_outcome="proposal", expect_action="allow",
                    expect_missing=["DMZ", "database-server"])
    state = _proposal_state(
        ProposedRule(name="r", action="deny"),  # wrong action
        unmet=["Source zone 'DMZ' exists in inventory"],  # missing database-server finding
    )

    checks = score_case(case, state)

    assert checks["action"] is False
    assert checks["missing"] is False
    assert not case_passed(checks)


def test_score_case_wrong_outcome():
    case = EvalCase(intent="gibberish", expect_outcome="halt@intent")
    assert score_case(case, _halted_at("redundancy")) == {"outcome": False}


def test_load_cases_round_trip(tmp_path):
    f = tmp_path / "cases.jsonl"
    f.write_text(
        '{"intent": "a", "expect_outcome": "halt@intent"}\n\n'
        '{"intent": "b", "expect_outcome": "proposal", "expect_action": "deny"}\n',
        encoding="utf-8",
    )

    cases = load_cases(f)

    assert [c.intent for c in cases] == ["a", "b"]
    assert cases[1].expect_action == "deny"
