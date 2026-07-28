# File: config/settings.py
from __future__ import annotations

from functools import lru_cache
from typing import Literal

try:
    from pydantic import AliasChoices, Field
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - dependency bootstrap fallback
    from pydantic import BaseSettings, Field  # type: ignore[assignment]
    AliasChoices = None  # type: ignore[assignment,misc]

    SettingsConfigDict = dict  # type: ignore[misc,assignment]


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = Field(default="AI Resume Automation Platform", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    app_env: Literal["development", "test", "staging", "production"] = Field(
        default="development",
        alias="APP_ENV",
    )
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    cors_origins: list[str] = Field(default=["*"], alias="CORS_ORIGINS")

    database_url: str = Field(
        default="sqlite:///./resume_automation.db",
        alias="DATABASE_URL",
        validation_alias=AliasChoices("DATABASE_URL", "POSTGRES_URL") if AliasChoices else "DATABASE_URL",
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
    llm_model_name: str = Field(default="llama3", alias="LLM_MODEL_NAME")
    ollama_small_model: str = Field(default="llama3.2:1b", alias="OLLAMA_SMALL_MODEL")
    ollama_large_model: str = Field(default="llama3.1:8b", alias="OLLAMA_LARGE_MODEL")

    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    huggingface_api_key: str | None = Field(
        default=None,
        alias="HF_API_KEY",
        validation_alias=AliasChoices("HF_API_KEY", "HUGGINGFACE_API_KEY") if AliasChoices else "HF_API_KEY",
    )
    langfuse_public_key: str | None = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    gmail_client_id: str | None = Field(
        default=None, alias="GMAIL_CLIENT_ID",
        validation_alias=AliasChoices("GMAIL_CLIENT_ID", "GOOGLE_CLIENT_ID") if AliasChoices else "GMAIL_CLIENT_ID",
    )
    gmail_client_secret: str | None = Field(
        default=None, alias="GMAIL_CLIENT_SECRET",
        validation_alias=AliasChoices("GMAIL_CLIENT_SECRET", "GOOGLE_CLIENT_SECRET") if AliasChoices else "GMAIL_CLIENT_SECRET",
    )
    gmail_refresh_token: str | None = Field(
        default=None, alias="GMAIL_REFRESH_TOKEN",
        validation_alias=AliasChoices("GMAIL_REFRESH_TOKEN", "GOOGLE_REFRESH_TOKEN") if AliasChoices else "GMAIL_REFRESH_TOKEN",
    )
    email_sender: str = Field(default="no-reply@example.com", alias="EMAIL_SENDER")
    auth_token_secret: str = Field(default="change-me-in-production", alias="AUTH_TOKEN_SECRET")

    celery_task_always_eager: bool = Field(default=True, alias="CELERY_TASK_ALWAYS_EAGER")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def google_client_id(self) -> str | None:
        """Backward-compatible Gmail client identifier accessor."""
        return self.gmail_client_id

    @property
    def google_client_secret(self) -> str | None:
        """Backward-compatible Gmail client-secret accessor."""
        return self.gmail_client_secret

    @property
    def google_refresh_token(self) -> str | None:
        """Backward-compatible Gmail refresh-token accessor."""
        return self.gmail_refresh_token


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
