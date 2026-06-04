"""Single-shot CLI for the SECURED agent (Portkey gateway + Prisma AIRS gate).

Same gauntlet as run_agent.py, plus: LLM calls routed through Portkey, and an
AIRS action gate that scans the intent and proposed rule before the approval
gate, halting on a block.

Run from repo root:
    uv run --group secured --env-file .env python \\
        packages/pan-os-agent/scripts/run_agent_secured.py "<intent>"
    uv run --group secured --env-file .env python \\
        packages/pan-os-agent/scripts/run_agent_secured.py \\
        --fixtures packages/pan-os-agent/fixtures/intents.txt
"""

import argparse
import asyncio
from pathlib import Path

from pan_os_agent.context import AgentContext
from pan_os_agent.driver import load_intents, render_outcome, run_intents
from pan_os_agent.mcp_client import McpClient
from pan_os_agent.security.airs import AirsScanner
from pan_os_agent.security.config import get_secured_settings
from pan_os_agent.security.gate import SECURED_STAGES
from pan_os_agent.security.gateway import build_portkey_anthropic
from pan_os_rag.retrieve import retrieve


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SECURED policy gauntlet.")
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

    settings = get_secured_settings()
    client = build_portkey_anthropic(settings)
    airs = AirsScanner(settings.airs_profile_name)
    async with McpClient() as mcp:
        ctx = AgentContext(
            mcp=mcp, retriever=retrieve, anthropic=client,
            model=settings.portkey_model, airs=airs,
        )
        results = await run_intents(intents, ctx, SECURED_STAGES)

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
