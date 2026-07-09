"""Single-shot CLI for the guided policy-authoring agent.

Runs the four-stage gauntlet over one intent or a fixtures file, prints a
human-readable outcome per intent, and optionally dumps full JSON traces.

The LLM path (direct Anthropic vs. Portkey self-hosted/cloud, with Prisma AIRS
as a gateway guardrail) is chosen entirely by env config via `build_llm_client`
— there is no separate "secured" CLI; set PORTKEY_MODE to switch.

Run from repo root:
    uv run --env-file .env python packages/pan-os-agent/scripts/run_agent.py \\
        "finance group needs access to Salesforce"
    uv run --env-file .env python packages/pan-os-agent/scripts/run_agent.py \\
        --fixtures packages/pan-os-agent/fixtures/intents.txt --out traces
"""

import argparse
import asyncio
from pathlib import Path

from pan_os_agent.context import AgentContext
from pan_os_agent.driver import load_intents, render_outcome, run_intents
from pan_os_agent.llm_client import build_llm_client, build_mcp_client, get_llm_settings
from pan_os_rag.retrieve import retrieve


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the policy-authoring gauntlet.")
    parser.add_argument("intent", nargs="?", help="a single natural-language intent")
    parser.add_argument("--fixtures", type=Path, help="file with one intent per line")
    parser.add_argument("--out", type=Path, help="directory to write JSON traces into")
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    if args.intent:
        intents = [args.intent]
    elif args.fixtures:
        intents = load_intents(args.fixtures)
    else:
        raise SystemExit("provide an intent argument or --fixtures FILE")

    settings = get_llm_settings()
    client = build_llm_client(settings)
    async with build_mcp_client(settings) as mcp:
        ctx = AgentContext(
            mcp=mcp, retriever=retrieve, anthropic=client, model=settings.call_model
        )
        results = await run_intents(intents, ctx)

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
    for i, state in enumerate(results):
        print(render_outcome(state))
        print()
        if args.out:
            (args.out / f"{i:02d}.json").write_text(
                state.model_dump_json(indent=2), encoding="utf-8"
            )


if __name__ == "__main__":
    asyncio.run(main())
