"""Shared Streamlit rendering for the agent demo apps.

Imports streamlit, so it is only ever loaded by the app entrypoint (never by
the core agent or its tests), keeping the GUI framework out of the library.
"""

import streamlit as st

from pan_os_agent.state import PolicyDraftState


def render_result(state: PolicyDraftState) -> None:
    st.write("**Stages run:** " + " → ".join(t.stage for t in state.trace))

    if state.halted:
        # An AIRS block (secured product) is a security event — make it stand out.
        if state.trace and state.trace[-1].stage == "security":
            st.error(f"🛡️ **Blocked by Prisma AIRS:** {state.halt_reason}")
        else:
            st.warning(f"**Halted:** {state.halt_reason}")
    else:
        rule = state.proposal.rule
        st.success(f"**Proposed rule:** `{rule.name}`  — pending approval, never committed")
        rows = [
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

    with st.expander("Full JSON trace"):
        st.json(state.model_dump())
