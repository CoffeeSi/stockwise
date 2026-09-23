"""Database configuration from environment variables or the root .env file."""

from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class CorsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def frontend_origins(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ))


class Settings(CorsSettings):
    database_url: str = Field(repr=False)
    db_echo: bool = False
    jwt_secret: SecretStr | None = None
    jwt_access_minutes: int = Field(default=30, ge=5, le=1440)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 15.0
    ai_cache_ttl_seconds: int = 300
    order_export_directory: Path = PROJECT_ROOT / "var" / "order-exports"
    import_spool_directory: Path = PROJECT_ROOT / "var" / "import-spool"

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value():
            return None
        if len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 bytes")
        return value

    @model_validator(mode="before")
    @classmethod
    def require_database_url(cls, values: dict[str, Any]) -> dict[str, Any]:
        url = values.get("database_url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError(
                "DATABASE_URL не задан. Укажите подключение PostgreSQL в .env "
                "или переменной окружения: "
                "postgresql+psycopg://user:password@localhost:5432/hackalem"
            )
        return values

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        value = value.strip()
        if value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+psycopg://", 1)
        message = (
            "DATABASE_URL должен быть корректным URL PostgreSQL с драйвером "
            "psycopg: postgresql+psycopg://user:password@localhost:5432/hackalem"
        )
        try:
            url = make_url(value)
        except (ArgumentError, ValueError):
            raise ValueError(message) from None
        if url.drivername != "postgresql+psycopg":
            raise ValueError(message)
        return value
