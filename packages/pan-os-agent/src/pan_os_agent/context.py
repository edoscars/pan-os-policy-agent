"""AgentContext: the dependency-injection seam for stages.

Every stage takes (state, ctx). The context bundles the three collaborators a
stage might need — the MCP client (firewall), the RAG retriever (docs), and the
Anthropic client (judgment) — so tests can inject fakes for each. It is a plain
dataclass, not a Pydantic model, because it holds live, non-serializable objects.
"""

from collections.abc import Callable
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from pan_os_agent.mcp_client import McpClient
from pan_os_rag.chunk import Chunk

# Both pan-os-rag retrievers share this signature: (query, k) -> list[Chunk].
Retriever = Callable[..., list[Chunk]]

DEFAULT_MODEL = "claude-sonnet-4-6"


@dataclass
class AgentContext:
    mcp: McpClient
    retriever: Retriever
    anthropic: AsyncAnthropic
    model: str = DEFAULT_MODEL
