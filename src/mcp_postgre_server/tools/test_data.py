from __future__ import annotations

import hashlib
import random
from typing import Any

from mcp_postgre_server.db import Database
from mcp_postgre_server.security.policies import ServerPolicy
from mcp_postgre_server.tools.schema import describe_table_impl


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _sample_value(column: dict[str, Any], row_index: int, rng: random.Random) -> Any:
    name = column["column_name"]
    dtype = column["data_type"].lower()
    if column.get("column_default") and "nextval" in str(column["column_default"]):
        return None
    if "uuid" in dtype:
        seed = hashlib.md5(f"{name}-{row_index}".encode(), usedforsecurity=False).hexdigest()
        return f"{seed[:8]}-{seed[8:12]}-{seed[12:16]}-{seed[16:20]}-{seed[20:32]}"
    if "int" in dtype:
        return row_index
    if "numeric" in dtype or "double" in dtype or "real" in dtype:
        return round(rng.random() * 1000, 2)
    if "bool" in dtype:
        return row_index % 2 == 0
    if "date" == dtype:
        return f"2026-01-{(row_index % 28) + 1:02d}"
    if "timestamp" in dtype:
        return f"2026-01-{(row_index % 28) + 1:02d}T12:00:00Z"
    if "json" in dtype:
        return '{"source":"mcp-postgre-server","row":%d}' % row_index
    return f"test_{name}_{row_index}"


async def generate_test_fixtures_impl(
    db: Database,
    policy: ServerPolicy,
    schema: str,
    table: str,
    rows: int = 3,
    seed: int = 42,
) -> dict[str, Any]:
    rows = max(1, min(rows, 100))
    metadata = await describe_table_impl(db, policy, schema, table)
    rng = random.Random(seed)
    insertable_columns = [
        col for col in metadata["columns"] if not (col.get("column_default") and "nextval" in str(col["column_default"]))
    ]
    if not insertable_columns:
        raise ValueError("no insertable columns discovered")

    col_names = [col["column_name"] for col in insertable_columns]
    statements = []
    for row_index in range(1, rows + 1):
        values = [_sample_value(col, row_index, rng) for col in insertable_columns]
        statement = (
            f"INSERT INTO {schema}.{table} ("
            + ", ".join(f'\"{name}\"' for name in col_names)
            + ") VALUES ("
            + ", ".join(_literal(value) for value in values)
            + ");"
        )
        statements.append(statement)

    return {
        "schema": schema,
        "table": table,
        "rows": rows,
        "seed": seed,
        "sql": "\n".join(statements),
    }


def register_test_data_tools(mcp: Any, db: Database, policy: ServerPolicy) -> None:
    @mcp.tool(name="postgres_generate_test_fixtures")
    async def postgres_generate_test_fixtures(
        schema: str,
        table: str,
        rows: int = 3,
        seed: int = 42,
    ) -> dict[str, Any]:
        """Generate deterministic PostgreSQL INSERT statements for unit/integration tests."""
        return await generate_test_fixtures_impl(db, policy, schema, table, rows, seed)
