"""Settings for the secured product (Portkey gateway + Prisma AIRS).

Separate from the core config so the unsecured product never requires these
keys. The Prisma AIRS API key is read by the aisecurity SDK directly from
PANW_AI_SEC_API_KEY, so it isn't modelled here.
"""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuredSettings(BaseSettings):
    portkey_api_key: SecretStr = Field(...)
    portkey_base_url: str = "https://api.portkey.ai"
    # Portkey references models by a catalog slug: @<provider>/<model>.
    portkey_model: str = "@anthropic/claude-opus-4-8"
    airs_profile_name: str = Field(...)

    model_config = SettingsConfigDict(env_file_encoding="utf-8", frozen=True)


@lru_cache(maxsize=1)
def get_secured_settings() -> SecuredSettings:
    return SecuredSettings()
