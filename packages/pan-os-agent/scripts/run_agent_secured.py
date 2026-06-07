"""Single-shot CLI for the SECURED agent (Portkey gateway + Prisma AIRS).

Same four-stage gauntlet as run_agent.py — the only difference is the client:
LLM calls are routed through a Portkey Config whose guardrails run Prisma AIRS.
AIRS scans each call's prompt *before* the model and the response after; a block
comes back as HTTP 446 and halts the run as a security event. AIRS is configured
in the Portkey GUI, so this needs no extra Python deps and no AIRS keys here.

Run from repo root:
    uv run --env-file .env python \\
        packages/pan-os-agent/scripts/run_agent_secured.py "<intent>"
    uv run --env-file .env python \\
        packages/pan-os-agent/scripts/run_agent_secured.py \\
        --fixtures packages/pan-os-agent/fixtures/intents.txt
"""

import argparse
import asyncio
from pathlib import Path

from pan_os_agent.context import AgentContext
from pan_os_agent.driver import load_intents, render_outcome, run_intents
from pan_os_agent.mcp_client import McpClient
from pan_os_agent.security.config import get_secured_settings
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
    async with McpClient() as mcp:
        # Same core gauntlet as the unsecured product; AIRS is enforced at the
        # gateway by the Portkey Config, not by an extra stage.
        ctx = AgentContext(
            mcp=mcp, retriever=retrieve, anthropic=client, model=settings.portkey_model
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
