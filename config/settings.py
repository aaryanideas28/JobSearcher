# File: config/settings.py
from __future__ import annotations

from functools import lru_cache
from typing import Literal

try:
    from pydantic import Field
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - dependency bootstrap fallback
    from pydantic import BaseSettings, Field  # type: ignore[assignment]

    SettingsConfigDict = dict  # type: ignore[misc,assignment]


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = Field(default="AI Resume Automation Platform", alias="APP_NAME")
    app_env: Literal["development", "test", "staging", "production"] = Field(
        default="development",
        alias="APP_ENV",
    )
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")

    database_url: str = Field(
        default="sqlite:///./resume_automation.db",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        alias="CELERY_BROKER_URL",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2",
        alias="CELERY_RESULT_BACKEND",
    )

    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_small_model: str = Field(default="llama3.2:1b", alias="OLLAMA_SMALL_MODEL")
    ollama_large_model: str = Field(default="llama3.1:8b", alias="OLLAMA_LARGE_MODEL")

    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    langfuse_public_key: str | None = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    google_client_id: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    google_refresh_token: str | None = Field(default=None, alias="GOOGLE_REFRESH_TOKEN")
    email_sender: str = Field(default="no-reply@example.com", alias="EMAIL_SENDER")
    auth_token_secret: str = Field(default="change-me-in-production", alias="AUTH_TOKEN_SECRET")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
