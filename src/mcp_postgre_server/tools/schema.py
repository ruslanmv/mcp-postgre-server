from __future__ import annotations

from typing import Any

from mcp_postgre_server.db import Database
from mcp_postgre_server.security.policies import ServerPolicy


async def list_schemas_impl(db: Database) -> list[dict[str, Any]]:
    return await db.fetch(
        """
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name = ANY($1::text[])
        ORDER BY schema_name
        """,
        db.settings.allowed_schemas,
    )


async def list_tables_impl(db: Database, policy: ServerPolicy, schema: str) -> list[dict[str, Any]]:
    decision = policy.schema_allowed(schema)
    if not decision.allowed:
        raise ValueError(decision.reason)
    return await db.fetch(
        """
        SELECT table_schema, table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = $1
        ORDER BY table_name
        """,
        schema,
    )


async def describe_table_impl(db: Database, policy: ServerPolicy, schema: str, table: str) -> dict[str, Any]:
    decision = policy.schema_allowed(schema)
    if not decision.allowed:
        raise ValueError(decision.reason)

    columns = await db.fetch(
        """
        SELECT
            column_name,
            data_type,
            udt_name,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
        """,
        schema,
        table,
    )
    if not columns:
        raise ValueError(f"table not found or not visible: {schema}.{table}")

    indexes = await db.fetch(
        """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = $1 AND tablename = $2
        ORDER BY indexname
        """,
        schema,
        table,
    )

    constraints = await db.fetch(
        """
        SELECT
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
         AND tc.table_name = kcu.table_name
        WHERE tc.table_schema = $1 AND tc.table_name = $2
        ORDER BY tc.constraint_name, kcu.ordinal_position
        """,
        schema,
        table,
    )

    foreign_keys = await db.fetch(
        """
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_schema AS foreign_table_schema,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = $1
          AND tc.table_name = $2
        ORDER BY tc.constraint_name, kcu.ordinal_position
        """,
        schema,
        table,
    )

    return {
        "schema": schema,
        "table": table,
        "columns": columns,
        "indexes": indexes,
        "constraints": constraints,
        "foreign_keys": foreign_keys,
    }


def register_schema_tools(mcp: Any, db: Database, policy: ServerPolicy) -> None:
    @mcp.tool(name="postgres_health")
    async def postgres_health() -> dict[str, Any]:
        """Check PostgreSQL connectivity and active server policy."""
        ok = await db.ping()
        return {
            "ok": ok,
            "server": db.settings.server_name,
            "read_only": db.settings.read_only,
            "allowed_schemas": db.settings.allowed_schemas,
            "max_rows": db.settings.max_rows,
        }

    @mcp.tool(name="postgres_list_schemas")
    async def postgres_list_schemas() -> list[dict[str, Any]]:
        """List PostgreSQL schemas allowed by server policy."""
        return await list_schemas_impl(db)

    @mcp.tool(name="postgres_list_tables")
    async def postgres_list_tables(schema: str = "public") -> list[dict[str, Any]]:
        """List tables and views in an allowed schema."""
        return await list_tables_impl(db, policy, schema)

    @mcp.tool(name="postgres_describe_table")
    async def postgres_describe_table(schema: str, table: str) -> dict[str, Any]:
        """Describe columns, indexes, constraints, and foreign keys for a table."""
        return await describe_table_impl(db, policy, schema, table)
