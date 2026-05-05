from __future__ import annotations

import re
from typing import Any

from mcp_postgre_server.security.policies import ServerPolicy

MIGRATION_SPLIT_RE = re.compile(r";\s*(?:\n|$)")


def split_migration(sql: str) -> list[str]:
    return [statement.strip() for statement in MIGRATION_SPLIT_RE.split(sql) if statement.strip()]


async def validate_migration_impl(policy: ServerPolicy, sql: str) -> dict[str, Any]:
    statements = split_migration(sql)
    if not statements:
        return {"valid": False, "reason": "migration is empty", "statements": []}

    decision = policy.validate_migration(sql)
    diagnostics = []
    for index, statement in enumerate(statements, start=1):
        upper = statement.upper()
        diagnostics.append(
            {
                "index": index,
                "statement_preview": statement[:200],
                "contains_create": "CREATE" in upper,
                "contains_alter": "ALTER" in upper,
                "contains_drop": "DROP" in upper,
                "contains_truncate": "TRUNCATE" in upper,
            }
        )

    return {
        "valid": decision.allowed,
        "reason": decision.reason,
        "statement_count": len(statements),
        "statements": diagnostics,
        "read_only_policy": policy.settings.read_only,
    }


def register_migration_tools(mcp: Any, policy: ServerPolicy) -> None:
    @mcp.tool(name="postgres_validate_migration")
    async def postgres_validate_migration(sql: str) -> dict[str, Any]:
        """Validate PostgreSQL migration SQL statically without executing it."""
        return await validate_migration_impl(policy, sql)
