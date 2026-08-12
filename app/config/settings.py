"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets come from the environment, never source code."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    app_env: str = "development"

    @property
    def has_llm_credentials(self) -> bool:
        return bool(self.google_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
