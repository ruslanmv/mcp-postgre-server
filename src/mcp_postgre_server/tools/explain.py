from __future__ import annotations

from typing import Any

from mcp_postgre_server.db import Database
from mcp_postgre_server.security.policies import ServerPolicy


async def explain_query_impl(
    db: Database,
    policy: ServerPolicy,
    sql: str,
    parameters: list[Any] | None = None,
    analyze: bool = False,
) -> dict[str, Any]:
    result = policy.validate_query(sql, allow_explain=False)
    if not result.allowed:
        raise ValueError(result.reason)
    if analyze and not db.settings.explain_analyze_allowed:
        raise ValueError("EXPLAIN ANALYZE is disabled by policy")

    prefix = "EXPLAIN (FORMAT JSON, ANALYZE FALSE)"
    if analyze:
        prefix = "EXPLAIN (FORMAT JSON, ANALYZE TRUE, BUFFERS TRUE)"
    rows = await db.fetch(f"{prefix} {result.normalized_sql}", *(parameters or []))
    return {
        "sql": result.normalized_sql,
        "analyze": analyze,
        "plan": rows[0].get("QUERY PLAN") if rows else None,
    }


def register_explain_tools(mcp: Any, db: Database, policy: ServerPolicy) -> None:
    @mcp.tool(name="postgres_explain_query")
    async def postgres_explain_query(
        sql: str,
        parameters: list[Any] | None = None,
        analyze: bool = False,
    ) -> dict[str, Any]:
        """Run a safe PostgreSQL EXPLAIN plan for a guarded read-only query."""
        return await explain_query_impl(db, policy, sql, parameters, analyze)
