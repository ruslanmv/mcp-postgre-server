from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

from mcp_postgre_server.config import Settings


class Database:
    """Async PostgreSQL connection pool wrapper."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._pool: asyncpg.Pool | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        async with self._lock:
            if self._pool is not None:
                return
            self._pool = await asyncpg.create_pool(
                dsn=self.settings.postgres_dsn,
                min_size=self.settings.pool_min_size,
                max_size=self.settings.pool_max_size,
                command_timeout=self.settings.query_timeout_seconds,
                server_settings={
                    "statement_timeout": str(self.settings.query_timeout_seconds * 1000),
                    "application_name": self.settings.server_name,
                },
            )

    async def close(self) -> None:
        async with self._lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        if self._pool is None:
            await self.connect()
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            yield conn

    async def fetch(self, sql: str, *args: Any, timeout: float | None = None) -> list[dict[str, Any]]:
        async with self.acquire() as conn:
            rows = await conn.fetch(sql, *args, timeout=timeout or self.settings.query_timeout_seconds)
            return [dict(row) for row in rows]

    async def fetchrow(self, sql: str, *args: Any, timeout: float | None = None) -> dict[str, Any] | None:
        async with self.acquire() as conn:
            row = await conn.fetchrow(sql, *args, timeout=timeout or self.settings.query_timeout_seconds)
            return dict(row) if row is not None else None

    async def execute(self, sql: str, *args: Any, timeout: float | None = None) -> str:
        async with self.acquire() as conn:
            return await conn.execute(sql, *args, timeout=timeout or self.settings.query_timeout_seconds)

    async def ping(self) -> bool:
        row = await self.fetchrow("SELECT 1 AS ok")
        return bool(row and row.get("ok") == 1)
