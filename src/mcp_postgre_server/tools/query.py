from __future__ import annotations

from typing import Any

from mcp_postgre_server.db import Database
from mcp_postgre_server.security.policies import ServerPolicy


async def safe_select_impl(
    db: Database,
    policy: ServerPolicy,
    sql: str,
    parameters: list[Any] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    result = policy.validate_query(sql)
    if not result.allowed:
        raise ValueError(result.reason)

    requested_limit = min(limit or db.settings.max_rows, db.settings.max_rows)
    wrapped_sql = f"SELECT * FROM ({result.normalized_sql}) AS _mcp_safe_query LIMIT {requested_limit}"
    rows = await db.fetch(wrapped_sql, *(parameters or []))
    return {
        "sql": result.normalized_sql,
        "rows": rows,
        "row_count": len(rows),
        "max_rows": db.settings.max_rows,
        "referenced_schemas": result.referenced_schemas,
    }


def register_query_tools(mcp: Any, db: Database, policy: ServerPolicy) -> None:
    @mcp.tool(name="postgres_safe_select")
    async def postgres_safe_select(
        sql: str,
        parameters: list[Any] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Execute one guarded, read-only SELECT-like PostgreSQL query with row limits."""
        return await safe_select_impl(db, policy, sql, parameters, limit)
