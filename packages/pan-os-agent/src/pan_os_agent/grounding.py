"""End-task grounding eval: score the agent's actual outcome against labels.

This evaluates the *product* — did the gauntlet reach the right outcome, propose
the right rule, and flag the right prerequisites/shadowing — rather than a
retrieval proxy like recall@k. Cases are labeled with robust expectations so
LLM non-determinism doesn't make the score flaky; checks only assert dimensions
that are deterministic given the firewall state.
"""

from pathlib import Path

from pydantic import BaseModel

from pan_os_agent.state import PolicyDraftState


class EvalCase(BaseModel):
    """One labeled intent. Empty/None expectation fields are not checked."""

    intent: str
    expect_outcome: str  # "proposal" | "halt@intent" | "halt@redundancy"
    expect_action: str = ""
    expect_applications: list[str] = []
    expect_user: str = ""
    expect_shadowed: bool | None = None
    expect_missing: list[str] = []  # substrings expected among unmet prereqs


def load_cases(path: Path) -> list[EvalCase]:
    """Read one JSON EvalCase per line."""
    return [
        EvalCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def outcome_of(state: PolicyDraftState) -> str:
    """Classify a finished run: a proposal, or a halt at the stage that stopped it."""
    if not state.halted:
        return "proposal"
    return f"halt@{state.trace[-1].stage}"


def score_case(case: EvalCase, state: PolicyDraftState) -> dict[str, bool]:
    """Return a named pass/fail check per labeled expectation for this case."""
    checks = {"outcome": outcome_of(state) == case.expect_outcome}

    # Rule/prereq checks only apply when a proposal was actually produced.
    if not state.halted and state.proposal is not None:
        rule = state.proposal.rule
        if case.expect_action:
            checks["action"] = rule.action == case.expect_action
        if case.expect_applications:
            checks["applications"] = all(a in rule.applications for a in case.expect_applications)
        if case.expect_user:
            checks["user"] = case.expect_user in rule.source_users
        if case.expect_shadowed is not None:
            checks["shadowed"] = state.proposal.shadow.shadowed == case.expect_shadowed
        if case.expect_missing:
            unmet = " ".join(
                f.requirement.lower()
                for f in (state.prerequisites.findings if state.prerequisites else [])
                if not f.satisfied
            )
            checks["missing"] = all(m.lower() in unmet for m in case.expect_missing)

    return checks


def case_passed(checks: dict[str, bool]) -> bool:
    return all(checks.values())
