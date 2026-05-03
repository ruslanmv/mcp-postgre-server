from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _csv(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    server_name: str = Field(default="mcp-postgre-server", alias="MCP_SERVER_NAME")
    server_host: str = Field(default="0.0.0.0", alias="MCP_SERVER_HOST")
    server_port: int = Field(default=8080, alias="MCP_SERVER_PORT")
    mount_path: str = Field(default="/mcp", alias="MCP_MOUNT_PATH")
    auth_token: str | None = Field(default=None, alias="MCP_AUTH_TOKEN")
    log_level: str = Field(default="INFO", alias="MCP_LOG_LEVEL")

    postgres_dsn: str = Field(alias="POSTGRES_DSN")
    allowed_schemas: Annotated[list[str], Field(default_factory=lambda: ["public"], alias="POSTGRES_ALLOWED_SCHEMAS")]
    read_only: bool = Field(default=True, alias="POSTGRES_READ_ONLY")
    block_ddl: bool = Field(default=True, alias="POSTGRES_BLOCK_DDL")
    block_dml: bool = Field(default=True, alias="POSTGRES_BLOCK_DML")
    max_rows: int = Field(default=100, ge=1, le=10_000, alias="POSTGRES_MAX_ROWS")
    query_timeout_seconds: int = Field(default=5, ge=1, le=120, alias="POSTGRES_QUERY_TIMEOUT_SECONDS")
    pool_min_size: int = Field(default=1, ge=1, le=50, alias="POSTGRES_POOL_MIN_SIZE")
    pool_max_size: int = Field(default=10, ge=1, le=100, alias="POSTGRES_POOL_MAX_SIZE")
    explain_analyze_allowed: bool = Field(default=False, alias="POSTGRES_EXPLAIN_ANALYZE_ALLOWED")

    @field_validator("allowed_schemas", mode="before")
    @classmethod
    def parse_allowed_schemas(cls, value: str | list[str]) -> list[str]:
        parsed = _csv(value)
        if not parsed:
            raise ValueError("POSTGRES_ALLOWED_SCHEMAS must contain at least one schema")
        return parsed

    @field_validator("mount_path")
    @classmethod
    def normalize_mount_path(cls, value: str) -> str:
        return value if value.startswith("/") else f"/{value}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
