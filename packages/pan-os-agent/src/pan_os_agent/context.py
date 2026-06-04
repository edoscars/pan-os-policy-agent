"""AgentContext: the dependency-injection seam for stages.

Every stage takes (state, ctx). The context bundles the three collaborators a
stage might need — the MCP client (firewall), the RAG retriever (docs), and the
Anthropic client (judgment) — so tests can inject fakes for each. It is a plain
dataclass, not a Pydantic model, because it holds live, non-serializable objects.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from anthropic import AsyncAnthropic

from pan_os_agent.mcp_client import McpClient
from pan_os_rag.chunk import Chunk

if TYPE_CHECKING:
    # Typed-only import: keeps the aisecurity SDK out of the core/unsecured path.
    from pan_os_agent.security.airs import AirsScanner

# Both pan-os-rag retrievers share this signature: (query, k) -> list[Chunk].
Retriever = Callable[..., list[Chunk]]

# Opus 4.8: most capable model; structured outputs + adaptive thinking supported.
# Override per-run via AgentContext.model (e.g. "claude-sonnet-4-6" for cheaper/faster).
DEFAULT_MODEL = "claude-opus-4-8"


@dataclass
class AgentContext:
    mcp: McpClient
    retriever: Retriever
    anthropic: AsyncAnthropic
    model: str = DEFAULT_MODEL
    # Set only by the secured product; the AIRS gate stage reads it.
    airs: "AirsScanner | None" = None
