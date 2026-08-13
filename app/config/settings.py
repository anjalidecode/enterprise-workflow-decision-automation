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
    app_version: str = "0.7.0"
    api_v1_prefix: str = "/api/v1"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    # Comma-separated origins for CORS. Do not use "*" in non-dev unless intentional.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173"

    # JWT — never hardcode a production secret; set JWT_SECRET_KEY in the environment.
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # PostgreSQL — required for auth and durable workflow/platform records (Module 5C).
    database_url: str = ""
    database_pool_size: int = 5
    database_max_overflow: int = 10

    @property
    def has_llm_credentials(self) -> bool:
        return bool(self.google_api_key.strip())

    @property
    def has_database_url(self) -> bool:
        return bool(self.database_url.strip())

    @property
    def require_database_url(self) -> str:
        """Return DATABASE_URL or raise a clear configuration error."""

        url = self.database_url.strip()
        if not url:
            raise RuntimeError(
                "DATABASE_URL is not configured. Set DATABASE_URL to a PostgreSQL "
                "SQLAlchemy URL (e.g. postgresql+psycopg://user:pass@localhost:5432/enterprise_workflow) "
                "before using persistent database operations."
            )
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_jwt_secret(self) -> str:
        """Return configured JWT secret, or a development-only fallback."""

        configured = self.jwt_secret_key.strip()
        if configured:
            return configured
        if self.app_env.strip().lower() in {"development", "test", "testing"}:
            # Explicitly insecure and local-only. Production must set JWT_SECRET_KEY.
            return "dev-only-insecure-jwt-secret-change-me"
        raise RuntimeError(
            "JWT_SECRET_KEY must be set when APP_ENV is not development/test."
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
