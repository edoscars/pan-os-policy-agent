"""Run the end-task grounding eval: agent vs labeled expectations.

Runs the gauntlet over eval/cases.jsonl and scores each run against its labels
(outcome, proposed-rule fields, flagged prerequisites/shadowing). Prints a
per-case scorecard and an overall pass rate. Unlike recall@k, this measures the
product the agent emits, not retrieval in isolation.

Run from repo root:
    uv run --env-file .env python packages/pan-os-agent/scripts/run_grounding_eval.py
"""

import asyncio
from pathlib import Path

from anthropic import AsyncAnthropic

from pan_os_agent.config import get_settings
from pan_os_agent.context import AgentContext
from pan_os_agent.grounding import case_passed, load_cases, outcome_of, score_case
from pan_os_agent.mcp_client import McpClient
from pan_os_agent.orchestrator import run_agent
from pan_os_agent.state import PolicyDraftState
from pan_os_rag.retrieve import retrieve

CASES_PATH = Path(__file__).resolve().parents[1] / "eval" / "cases.jsonl"


async def main() -> None:
    cases = load_cases(CASES_PATH)
    client = AsyncAnthropic(api_key=get_settings().anthropic_api_key.get_secret_value())

    passed = 0
    async with McpClient() as mcp:
        ctx = AgentContext(mcp=mcp, retriever=retrieve, anthropic=client)
        for case in cases:
            state = await run_agent(PolicyDraftState(intent_text=case.intent), ctx)
            checks = score_case(case, state)
            ok = case_passed(checks)
            passed += ok
            mark = "PASS" if ok else "FAIL"
            failed = [name for name, good in checks.items() if not good]
            detail = f" (failed: {', '.join(failed)}; got {outcome_of(state)})" if failed else ""
            print(f"[{mark}] {case.intent[:60]}{detail}")

    print(f"\nGrounding eval: {passed}/{len(cases)} cases passed")


if __name__ == "__main__":
    asyncio.run(main())
