"""Settings for the secured product (Portkey gateway).

Separate from the core config so the unsecured product never requires these.
Prisma AIRS is configured entirely in the Portkey GUI (Guardrails) and attached
to the Config referenced by `portkey_config` — there are no AIRS keys here.
"""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuredSettings(BaseSettings):
    portkey_api_key: SecretStr = Field(...)
    portkey_base_url: str = "https://api.portkey.ai"
    # Portkey references models by a catalog slug: @<provider>/<model>.
    portkey_model: str = "@anthropic/claude-opus-4-8"
    # Portkey Config ID (pc-***) whose input/output guardrails run Prisma AIRS.
    portkey_config: str = Field(...)
    # Optional: Portkey MCP gateway URL (https://mcp.portkey.ai/<slug>/mcp). When
    # set, the secured agent routes its firewall tool calls through Portkey so
    # they're logged/governed there; when empty, it spawns the server over stdio.
    portkey_mcp_url: str = ""

    model_config = SettingsConfigDict(env_file_encoding="utf-8", frozen=True)


@lru_cache(maxsize=1)
def get_secured_settings() -> SecuredSettings:
    return SecuredSettings()
