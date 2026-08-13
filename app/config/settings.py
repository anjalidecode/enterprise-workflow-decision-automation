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
    app_name: str = "enterprise-workflow-decision-automation"
    app_version: str = "0.5.0"
    api_v1_prefix: str = "/api/v1"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    # Comma-separated origins for CORS. Do not use "*" in non-dev unless intentional.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173"

    @property
    def has_llm_credentials(self) -> bool:
        return bool(self.google_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
