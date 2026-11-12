
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str

    # Optional until live SerpApi discovery is enabled.
    serpapi_api_key: str | None = None

    gemini_api_key: SecretStr | None = None
    gemini_model: str = Field(
        default="gemini-3.8-flash", pattern=r"^gemini-[A-Za-z0-9._-]+$",
    )

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
