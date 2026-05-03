from __future__ import annotations

import json
from typing import Any

from mcp_postgre_server.db import Database
from mcp_postgre_server.security.policies import ServerPolicy
from mcp_postgre_server.tools.schema import describe_table_impl, list_schemas_impl, list_tables_impl


def register_database_resources(mcp: Any, db: Database, policy: ServerPolicy) -> None:
    @mcp.resource("postgres://schemas")
    async def postgres_schemas_resource() -> str:
        """Allowed PostgreSQL schemas as JSON."""
        return json.dumps(await list_schemas_impl(db), default=str, indent=2)

    @mcp.resource("postgres://schema/{schema}")
    async def postgres_schema_resource(schema: str) -> str:
        """Tables and views in an allowed PostgreSQL schema as JSON."""
        return json.dumps(await list_tables_impl(db, policy, schema), default=str, indent=2)

    @mcp.resource("postgres://table/{schema}/{table}")
    async def postgres_table_resource(schema: str, table: str) -> str:
        """Table metadata as JSON."""
        return json.dumps(await describe_table_impl(db, policy, schema, table), default=str, indent=2)
