from __future__ import annotations

from dataclasses import dataclass

from mcp_postgre_server.config import Settings
from mcp_postgre_server.security.sql_guard import SQLGuardResult, validate_sql


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


class ServerPolicy:
    """Centralized security policy for tools and SQL operations."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def schema_allowed(self, schema: str) -> PolicyDecision:
        if schema in self.settings.allowed_schemas:
            return PolicyDecision(True, "schema allowed")
        return PolicyDecision(False, f"schema '{schema}' is not in allowlist")

    def validate_query(self, sql: str, *, allow_explain: bool = False) -> SQLGuardResult:
        return validate_sql(
            sql,
            allowed_schemas=self.settings.allowed_schemas,
            read_only=self.settings.read_only,
            block_ddl=self.settings.block_ddl,
            block_dml=self.settings.block_dml,
            allow_explain=allow_explain,
            allow_explain_analyze=self.settings.explain_analyze_allowed,
        )

    def validate_migration(self, sql: str) -> PolicyDecision:
        if self.settings.read_only:
            blocked = ["DROP", "TRUNCATE", "GRANT", "REVOKE", "COPY", "CALL", "DO"]
        else:
            blocked = ["DROP", "TRUNCATE"]
        upper = sql.upper()
        for keyword in blocked:
            if keyword in upper:
                return PolicyDecision(False, f"migration contains blocked keyword: {keyword}")
        return PolicyDecision(True, "migration passes static policy validation")
