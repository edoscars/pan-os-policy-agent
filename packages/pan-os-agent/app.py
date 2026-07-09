"""Streamlit demo UI for the guided policy-authoring agent.

A thin presentation layer over the same gauntlet the CLI runs: describe an
access need in plain English, see the validated outcome against the live
firewall. The agent never commits (v1).

Run from repo root:
    uv run --group demo --env-file .env streamlit run packages/pan-os-agent/app.py
"""

import asyncio

import streamlit as st

from pan_os_agent.context import AgentContext
from pan_os_agent.llm_client import build_llm_client, build_mcp_client, get_llm_settings
from pan_os_agent.orchestrator import run_agent
from pan_os_agent.state import PolicyDraftState
from pan_os_agent.ui import render_result
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
        settings = get_llm_settings()
        client = build_llm_client(settings)
        async with build_mcp_client(settings) as mcp:
            ctx = AgentContext(
                mcp=mcp, retriever=retrieve, anthropic=client, model=settings.call_model
            )
            return await run_agent(PolicyDraftState(intent_text=intent_text), ctx)

    return asyncio.run(_run())


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
    render_result(state)
