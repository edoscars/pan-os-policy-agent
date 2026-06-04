"""Streamlit demo UI for the guided policy-authoring agent.

A thin presentation layer over the same gauntlet the CLI runs: describe an
access need in plain English, see the validated outcome against the live
firewall. The agent never commits (v1).

Run from repo root:
    uv run --group demo --env-file .env streamlit run packages/pan-os-agent/app.py
"""

import asyncio

import streamlit as st
from anthropic import AsyncAnthropic

from pan_os_agent.config import get_settings
from pan_os_agent.context import AgentContext
from pan_os_agent.mcp_client import McpClient
from pan_os_agent.orchestrator import run_agent
from pan_os_agent.state import PolicyDraftState
from pan_os_rag.retrieve import retrieve

EXAMPLES = [
    "Block the BitTorrent application for engineering from trust to untrust",
    "Allow the finance group to reach Salesforce",
    "Permit web-browsing from the trust zone to the untrust zone",
    "Allow the DMZ zone to reach the database-server object over MySQL",
]


def run_gauntlet(intent_text: str) -> PolicyDraftState:
    """Run the four-stage gauntlet once for an intent (one MCP server spawn)."""

    async def _run() -> PolicyDraftState:
        client = AsyncAnthropic(api_key=get_settings().anthropic_api_key.get_secret_value())
        async with McpClient() as mcp:
            ctx = AgentContext(mcp=mcp, retriever=retrieve, anthropic=client)
            return await run_agent(PolicyDraftState(intent_text=intent_text), ctx)

    return asyncio.run(_run())


def render(state: PolicyDraftState) -> None:
    st.write("**Stages run:** " + " → ".join(t.stage for t in state.trace))

    if state.halted:
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


st.set_page_config(page_title="PAN-OS Policy Agent", page_icon="🛡️")
st.title("🛡️ Guided Security Policy Authoring")
st.caption(
    "Describe an access need in plain English. The agent validates it against your "
    "live firewall and RAG docs, then proposes a Security rule — it never commits (v1)."
)

example = st.selectbox("Pick an example, or write your own below:", [""] + EXAMPLES)
intent = st.text_input("Policy intent", value=example, placeholder="e.g. Let the HR team reach Workday")

if st.button("Run gauntlet", type="primary") and intent.strip():
    with st.spinner("Inspecting the firewall, retrieving docs, reasoning…"):
        state = run_gauntlet(intent.strip())
    render(state)
