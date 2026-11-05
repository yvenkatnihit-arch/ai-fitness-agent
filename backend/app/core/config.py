"""App settings, loaded from environment variables (and backend/.env in development).

Every secret and environment-specific value lives here. Safety limits do NOT:
those are in app/safety/safety_config.py and are not configurable per environment.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: Literal["development", "test", "production"] = "development"
    # NoDecode: read the raw "a,b" string so the validator below can split it.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # Gemini
    gemini_api_key: SecretStr
    gemini_small_model: str
    gemini_mid_model: str

    # Supabase
    supabase_url: str
    supabase_publishable_key: SecretStr
    supabase_secret_key: SecretStr
    database_url: SecretStr

    # LangSmith (optional)
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "ai-fitness-agent"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_comma_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Load settings once and reuse them. Fails fast if a required value is missing."""
    return Settings()
