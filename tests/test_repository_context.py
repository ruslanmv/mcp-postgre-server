"""Tests for postgres.generate_repository_context.

Uses a faked describe_table response so the tests don't need a live
postgres connection.
"""
from __future__ import annotations

from typing import Any

import pytest

from mcp_postgre_server.tools import repository


class _FakeDescribe:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    async def __call__(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.payload


@pytest.fixture
def users_metadata() -> dict[str, Any]:
    return {
        "schema": "public",
        "table": "users",
        "columns": [
            {
                "column_name": "id",
                "data_type": "uuid",
                "is_nullable": "NO",
                "column_default": "gen_random_uuid()",
            },
            {
                "column_name": "email",
                "data_type": "varchar",
                "is_nullable": "NO",
                "column_default": None,
            },
            {
                "column_name": "is_active",
                "data_type": "boolean",
                "is_nullable": "YES",
                "column_default": "true",
            },
            {
                "column_name": "created_at",
                "data_type": "timestamp with time zone",
                "is_nullable": "NO",
                "column_default": "CURRENT_TIMESTAMP",
            },
        ],
        "primary_key": ["id"],
        "foreign_keys": [],
    }


@pytest.mark.asyncio
async def test_python_scaffolding(monkeypatch, users_metadata):
    monkeypatch.setattr(repository, "describe_table_impl", _FakeDescribe(users_metadata))
    result = await repository.generate_repository_context_impl(
        db=None, policy=None, schema="public", table="users", language="python"
    )
    assert result["class_name"] == "Users"
    assert "class Users(BaseModel):" in result["model"]
    assert "id: UUID" in result["model"]
    assert "email: str" in result["model"]
    assert "is_active: bool | None = None" in result["model"]
    assert "class UsersRepository:" in result["repository"]
    assert "get_by_email" in result["suggested_methods"]
    assert result["primary_key"] == ["id"]


@pytest.mark.asyncio
async def test_typescript_scaffolding(monkeypatch, users_metadata):
    monkeypatch.setattr(repository, "describe_table_impl", _FakeDescribe(users_metadata))
    result = await repository.generate_repository_context_impl(
        db=None, policy=None, schema="public", table="users", language="typescript"
    )
    assert result["language"] == "typescript"
    assert "export interface Users" in result["model"]
    assert "email: string;" in result["model"]
    assert "is_active: boolean | null;" in result["model"]


@pytest.mark.asyncio
async def test_unsupported_language_rejected(monkeypatch, users_metadata):
    monkeypatch.setattr(repository, "describe_table_impl", _FakeDescribe(users_metadata))
    with pytest.raises(ValueError, match="Unsupported language"):
        await repository.generate_repository_context_impl(
            db=None, policy=None, schema="public", table="users", language="cobol"
        )


@pytest.mark.asyncio
async def test_table_without_email_drops_get_by_email(monkeypatch):
    metadata = {
        "schema": "public",
        "table": "orders",
        "columns": [
            {"column_name": "id", "data_type": "uuid", "is_nullable": "NO", "column_default": None},
            {"column_name": "amount", "data_type": "numeric", "is_nullable": "NO", "column_default": None},
        ],
        "primary_key": ["id"],
        "foreign_keys": [],
    }
    monkeypatch.setattr(repository, "describe_table_impl", _FakeDescribe(metadata))
    result = await repository.generate_repository_context_impl(
        db=None, policy=None, schema="public", table="orders"
    )
    assert "get_by_email" not in result["suggested_methods"]
    assert result["class_name"] == "Orders"
