"""Shared Streamlit rendering for the agent demo app.

Imports streamlit, so it is only ever loaded by the app entrypoint (never by
the core agent or its tests), keeping the GUI framework out of the library.

Two rendering surfaces:
  - `render_stage_card` shows one gauntlet stage in plain English (used live, as
    each stage completes, and again in the final recap).
  - `render_result` shows the terminal outcome: the proposed rule table, the
    simulated approval, prerequisite/shadow caveats, and the raw JSON trace.
"""

import streamlit as st

from pan_os_agent.orchestrator import STAGE_LABELS
from pan_os_agent.state import PolicyDraftState

# Per-stage plain-English explanation, pulled from the structured stage output on
# the state rather than the terse trace summary.


def _intent_detail(state: PolicyDraftState) -> str:
    si = state.structured_intent
    if si is None:
        return "The request could not be parsed into an access-control intent."
    return f"Parsed intent: **{si.summary or state.intent_text}** (action: `{si.action}`)."


def _prerequisite_detail(state: PolicyDraftState) -> str:
    report = state.prerequisites
    if report is None:
        return "Not run."
    lines = []
    for f in report.findings:
        mark = "✅" if f.satisfied else "⚠️"
        detail = f" — {f.detail}" if f.detail else ""
        lines.append(f"{mark} {f.requirement}{detail}")
    header = (
        "All prerequisites are satisfied."
        if report.all_satisfied
        else "Some prerequisites are **not** satisfied (carried forward as caveats):"
    )
    return header + ("\n\n" + "\n".join(lines) if lines else "")


def _redundancy_detail(state: PolicyDraftState) -> str:
    report = state.redundancy
    if report is None:
        return "Not run."
    if report.redundant:
        return (
            f"An existing rule already covers this intent: "
            f"**`{report.matching_rule}`**.\n\n{report.reasoning}"
        )
    return f"No existing rule already satisfies the intent.\n\n{report.reasoning}"


def _proposal_detail(state: PolicyDraftState) -> str:
    proposal = state.proposal
    if proposal is None:
        return "Not run."
    line = f"Proposed rule **`{proposal.rule.name}`**."
    if proposal.shadow.shadowed:
        line += (
            f"\n\n⚠️ **Shadowing:** would be shadowed by "
            f"`{proposal.shadow.shadowing_rule}` and never take effect. "
            f"{proposal.shadow.reasoning}"
        )
    else:
        line += " No earlier rule would shadow it."
    return line


_STAGE_DETAIL = {
    "intent": _intent_detail,
    "prerequisite": _prerequisite_detail,
    "redundancy": _redundancy_detail,
    "proposal": _proposal_detail,
}


def render_stage_card(state: PolicyDraftState, stage_name: str) -> None:
    """Render one completed stage as an expandable, plain-English card."""
    label = STAGE_LABELS.get(stage_name, stage_name)
    halted_here = bool(
        state.halted and state.trace and state.trace[-1].stage == stage_name
    )

    if stage_name == "security":
        st.error(f"🛡️ **{label} — BLOCKED**")
        with st.expander("Why", expanded=True):
            st.write(state.halt_reason)
        return

    icon = "🛑" if halted_here else "✅"
    with st.expander(f"{icon} {label}", expanded=halted_here):
        detail_fn = _STAGE_DETAIL.get(stage_name)
        if detail_fn:
            st.markdown(detail_fn(state))
        if halted_here:
            st.warning(f"**Halted here:** {state.halt_reason}")

    if stage_name == "prerequisite" and state.prerequisites:
        _render_rag_panel(state)


def _render_rag_panel(state: PolicyDraftState) -> None:
    if state.prerequisites is None:
        return
    doc_ids = state.prerequisites.retrieved_doc_ids
    if not doc_ids:
        return
    with st.expander(f"📚 Retrieved documentation ({len(doc_ids)} chunks)", expanded=False):
        st.caption("RAG chunks that grounded the prerequisite check, most relevant first:")
        for i, doc_id in enumerate(doc_ids, 1):
            st.markdown(f"{i}. `{doc_id}`")


def render_airs_badge(state: PolicyDraftState, *, enabled: bool) -> None:
    """Show the AIRS scan verdict as a prominent badge, not buried in the trace."""
    if not enabled:
        st.info(
            "🛡️ **Prisma AIRS: not configured** — running without input/output "
            "scanning. Enable a Portkey path with an AIRS guardrail to scan."
        )
        return
    blocked = state.halted and state.trace and state.trace[-1].stage == "security"
    if blocked:
        st.error(f"🛡️ **Prisma AIRS: BLOCKED** — {state.halt_reason}")
    else:
        st.success("🛡️ **Prisma AIRS: allowed** — input and output scanned, no violation.")


def render_result(state: PolicyDraftState) -> None:
    """Render the terminal outcome of a run (proposal or halt) plus the raw trace."""
    if state.halted:
        if state.trace and state.trace[-1].stage == "security":
            st.error(f"🛡️ **Blocked by Prisma AIRS:** {state.halt_reason}")
        else:
            st.warning(f"**Halted:** {state.halt_reason}")
    elif state.proposal is not None:
        _render_proposal(state)

    with st.expander("Raw JSON trace"):
        st.json(state.model_dump())


def _render_proposal(state: PolicyDraftState) -> None:
    if state.proposal is None:
        return
    rule = state.proposal.rule
    st.success(f"**Proposed rule:** `{rule.name}` — pending approval, never committed")
    rows = [
        ("Name", rule.name),
        ("From → To", f"{', '.join(rule.from_zones)} → {', '.join(rule.to_zones)}"),
        ("Source → Dest", f"{', '.join(rule.sources)} → {', '.join(rule.destinations)}"),
        ("User", ", ".join(rule.source_users)),
        ("Application", ", ".join(rule.applications)),
        ("Service", ", ".join(rule.services)),
        ("Action", rule.action),
    ]
    st.table([{"Field": k, "Value": v} for k, v in rows])

    if state.prerequisites and not state.prerequisites.all_satisfied:
        unmet = [f.requirement for f in state.prerequisites.findings if not f.satisfied]
        st.warning("**Prerequisites not met:**\n" + "\n".join(f"- {u}" for u in unmet))

    if state.proposal.shadow.shadowed:
        st.error(
            f"**Shadowing warning:** this rule would be shadowed by "
            f"`{state.proposal.shadow.shadowing_rule}` and never take effect.\n\n"
            f"{state.proposal.shadow.reasoning}"
        )

    st.divider()
    _render_simulated_approval(rule.name)


def _render_simulated_approval(rule_name: str) -> None:
    st.button(
        "✅ Approve (simulated — does NOT touch the firewall)",
        type="primary",
        help=(
            "v1 never writes to the firewall. This records approval in the demo "
            "session only; no commit or candidate config is pushed to PAN-OS."
        ),
        key="approve",
    )
    if st.session_state.get("approve"):
        st.info(
            f"✔️ Approval recorded for `{rule_name}` **in this demo session only**. "
            "No configuration was pushed to the firewall (that is deferred to v2)."
        )
