"""Light types shared by the security layer (no heavy SDK imports).

Kept separate so the security_gate stage and its tests can use AirsVerdict
without importing the aisecurity SDK.
"""

from pydantic import BaseModel


class AirsVerdict(BaseModel):
    """The result of a Prisma AIRS scan, reduced to what the gate needs."""

    blocked: bool
    category: str = ""
    detail: str = ""
