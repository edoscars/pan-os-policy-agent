from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict 
from functools import lru_cache

class Settings(BaseSettings):
    voyage_api_key : SecretStr = Field(...)
    model_config = SettingsConfigDict(env_file_encoding="utf-8", frozen=True)

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

if __name__ == "__main__":
    try:
        settings = get_settings()
        print(settings.model_dump())
    except Exception as e:
        print(f"Error: {e}")