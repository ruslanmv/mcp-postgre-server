from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp

DDL_KEYWORDS = {
    "ALTER",
    "CREATE",
    "DROP",
    "TRUNCATE",
    "COMMENT",
    "REINDEX",
    "CLUSTER",
    "VACUUM",
    "ANALYZE",
}

DML_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "CALL",
    "DO",
    "COPY",
    "EXECUTE",
    "PREPARE",
    "DEALLOCATE",
    "LISTEN",
    "NOTIFY",
    "UNLISTEN",
    "SET",
    "RESET",
    "GRANT",
    "REVOKE",
}

DANGEROUS_PATTERNS = [
    re.compile(r"/\*.*?\*/", re.DOTALL),
    re.compile(r"--.*?$", re.MULTILINE),
    re.compile(r"\bpg_sleep\s*\(", re.IGNORECASE),
    re.compile(r"\bdblink\s*\(", re.IGNORECASE),
    re.compile(r"\blo_import\s*\(", re.IGNORECASE),
    re.compile(r"\blo_export\s*\(", re.IGNORECASE),
    re.compile(r"\bprogram\b", re.IGNORECASE),
]


@dataclass(frozen=True)
class SQLGuardResult:
    allowed: bool
    reason: str
    normalized_sql: str | None = None
    referenced_schemas: list[str] = field(default_factory=list)


class SQLGuardError(ValueError):
    """Raised when SQL violates server policy."""


def _strip_comments(sql: str) -> str:
    stripped = sql
    for pattern in DANGEROUS_PATTERNS[:2]:
        stripped = pattern.sub(" ", stripped)
    return stripped.strip()


def _first_keyword(sql: str) -> str:
    match = re.match(r"^\s*([a-zA-Z_]+)", sql)
    return match.group(1).upper() if match else ""


def _has_multiple_statements(sql: str) -> bool:
    statements = [part.strip() for part in sqlglot.transpile(sql, read="postgres")]
    return len(statements) > 1


def _extract_schemas(parsed: exp.Expression) -> list[str]:
    schemas: set[str] = set()
    for table in parsed.find_all(exp.Table):
        db = table.args.get("db")
        if db:
            schemas.add(str(db).strip('"'))
    return sorted(schemas)


def validate_sql(
    sql: str,
    *,
    allowed_schemas: list[str],
    read_only: bool = True,
    block_ddl: bool = True,
    block_dml: bool = True,
    allow_explain: bool = False,
    allow_explain_analyze: bool = False,
) -> SQLGuardResult:
    """Validate SQL against a conservative PostgreSQL policy."""

    if not sql or not sql.strip():
        return SQLGuardResult(False, "SQL is empty")

    raw = sql.strip()
    for pattern in DANGEROUS_PATTERNS[2:]:
        if pattern.search(raw):
            return SQLGuardResult(False, f"SQL contains blocked pattern: {pattern.pattern}")

    cleaned = _strip_comments(raw)
    if not cleaned:
        return SQLGuardResult(False, "SQL contains only comments")

    if ";" in cleaned.rstrip(";"):
        return SQLGuardResult(False, "Multiple statements are not allowed")

    try:
        parsed_statements = sqlglot.parse(cleaned, read="postgres")
    except Exception as exc:  # noqa: BLE001
        return SQLGuardResult(False, f"SQL parse failed: {exc}")

    if len(parsed_statements) != 1:
        return SQLGuardResult(False, "Exactly one SQL statement is required")

    parsed = parsed_statements[0]
    keyword = _first_keyword(cleaned)

    explain_requested = keyword == "EXPLAIN"
    if explain_requested and not allow_explain:
        return SQLGuardResult(False, "EXPLAIN is not allowed for this operation")

    if explain_requested and re.search(r"\bANALYZE\b", cleaned, re.IGNORECASE) and not allow_explain_analyze:
        return SQLGuardResult(False, "EXPLAIN ANALYZE is disabled")

    if block_ddl and keyword in DDL_KEYWORDS:
        return SQLGuardResult(False, f"DDL statement blocked: {keyword}")

    if block_dml and keyword in DML_KEYWORDS:
        return SQLGuardResult(False, f"DML/control statement blocked: {keyword}")

    if read_only and keyword not in {"SELECT", "WITH", "SHOW", "EXPLAIN"}:
        return SQLGuardResult(False, f"Read-only mode blocks statement: {keyword}")

    if isinstance(parsed, (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter)):
        return SQLGuardResult(False, "Mutation or DDL expression blocked")

    referenced_schemas = _extract_schemas(parsed)
    disallowed = [schema for schema in referenced_schemas if schema not in allowed_schemas]
    if disallowed:
        return SQLGuardResult(False, f"Schemas not allowed: {', '.join(disallowed)}", referenced_schemas=referenced_schemas)

    normalized = parsed.sql(dialect="postgres")
    return SQLGuardResult(True, "SQL allowed", normalized_sql=normalized, referenced_schemas=referenced_schemas)


def assert_sql_allowed(sql: str, **kwargs: Any) -> SQLGuardResult:
    result = validate_sql(sql, **kwargs)
    if not result.allowed:
        raise SQLGuardError(result.reason)
    return result
