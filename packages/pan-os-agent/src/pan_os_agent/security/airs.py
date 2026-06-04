"""Prisma AIRS scanner — the only module that imports the aisecurity SDK.

Isolated here so the core agent and its tests never depend on pan-aisecurity:
the security_gate stage calls scan() duck-typed through AgentContext.airs, and
tests inject a fake. Grounded in pan.dev's AIRS Python SDK usage guide.
"""

import asyncio

import aisecurity
from aisecurity.generated_openapi_client.models.ai_profile import AiProfile
from aisecurity.scan.inline.scanner import Scanner
from aisecurity.scan.models.content import Content

from pan_os_agent.security.types import AirsVerdict


class AirsScanner:
    """Wraps the AIRS inline scanner behind an async scan() -> AirsVerdict."""

    def __init__(self, profile_name: str) -> None:
        aisecurity.init()  # reads the API key from PANW_AI_SEC_API_KEY
        self._scanner = Scanner()
        self._profile = AiProfile(profile_name=profile_name)

    async def scan(self, prompt: str, response: str) -> AirsVerdict:
        """Scan the user input (prompt) and the agent's proposed action (response).

        sync_scan is the real-time inline call that returns a verdict directly;
        run it in a worker thread so it doesn't block the event loop.
        """
        result = await asyncio.to_thread(
            self._scanner.sync_scan,
            ai_profile=self._profile,
            content=Content(prompt=prompt, response=response),
        )
        return AirsVerdict(
            blocked=result.action == "block",
            category=result.category or "",
            detail=f"prompt={result.prompt_detected} response={result.response_detected}",
        )
