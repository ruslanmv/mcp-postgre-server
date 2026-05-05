"""Repository-pattern code scaffolding from a real table schema.

GitPilot's Coder agent calls ``postgres.generate_repository_context`` when
asked to generate a CRUD class for a table. Returning structured pieces
(model fields, suggested methods, FKs, PK columns) lets the LLM produce
code that lines up with the real database without hallucinating columns.

The tool is read-only: it relies entirely on ``describe_table_impl`` and
performs no writes.
"""
from __future__ import annotations

from typing import Any

from mcp_postgre_server.db import Database
from mcp_postgre_server.security.policies import ServerPolicy
from mcp_postgre_server.tools.schema import describe_table_impl

PY_TYPE_MAP: dict[str, str] = {
    "uuid": "UUID",
    "text": "str",
    "varchar": "str",
    "character varying": "str",
    "character": "str",
    "bpchar": "str",
    "citext": "str",
    "smallint": "int",
    "integer": "int",
    "bigint": "int",
    "serial": "int",
    "bigserial": "int",
    "smallserial": "int",
    "real": "float",
    "double precision": "float",
    "numeric": "Decimal",
    "decimal": "Decimal",
    "boolean": "bool",
    "bool": "bool",
    "date": "date",
    "time": "time",
    "timestamp": "datetime",
    "timestamp with time zone": "datetime",
    "timestamp without time zone": "datetime",
    "timestamptz": "datetime",
    "json": "dict[str, Any]",
    "jsonb": "dict[str, Any]",
    "bytea": "bytes",
}

TS_TYPE_MAP: dict[str, str] = {
    "uuid": "string",
    "text": "string",
    "varchar": "string",
    "character varying": "string",
    "character": "string",
    "bpchar": "string",
    "citext": "string",
    "smallint": "number",
    "integer": "number",
    "bigint": "number",
    "serial": "number",
    "bigserial": "number",
    "real": "number",
    "double precision": "number",
    "numeric": "number",
    "decimal": "number",
    "boolean": "boolean",
    "bool": "boolean",
    "date": "Date",
    "time": "string",
    "timestamp": "Date",
    "timestamp with time zone": "Date",
    "timestamp without time zone": "Date",
    "timestamptz": "Date",
    "json": "Record<string, unknown>",
    "jsonb": "Record<string, unknown>",
    "bytea": "Uint8Array",
}

JAVA_TYPE_MAP: dict[str, str] = {
    "uuid": "UUID",
    "text": "String",
    "varchar": "String",
    "character varying": "String",
    "character": "String",
    "smallint": "Short",
    "integer": "Integer",
    "bigint": "Long",
    "real": "Float",
    "double precision": "Double",
    "numeric": "BigDecimal",
    "decimal": "BigDecimal",
    "boolean": "Boolean",
    "date": "LocalDate",
    "time": "LocalTime",
    "timestamp": "Instant",
    "timestamp with time zone": "Instant",
    "timestamp without time zone": "LocalDateTime",
    "timestamptz": "Instant",
    "json": "String",
    "jsonb": "String",
    "bytea": "byte[]",
}

LANG_MAP: dict[str, dict[str, str]] = {
    "python": PY_TYPE_MAP,
    "typescript": TS_TYPE_MAP,
    "java": JAVA_TYPE_MAP,
}

_PY_FALLBACK = "Any"
_TS_FALLBACK = "unknown"
_JAVA_FALLBACK = "Object"
_FALLBACKS = {"python": _PY_FALLBACK, "typescript": _TS_FALLBACK, "java": _JAVA_FALLBACK}


def _camel_case(snake: str) -> str:
    return "".join(part.capitalize() for part in snake.split("_") if part)


def _map_type(language: str, sql_type: str) -> str:
    base = sql_type.split("(")[0].strip().lower()
    return LANG_MAP[language].get(base, _FALLBACKS[language])


def _python_model(class_name: str, columns: list[dict[str, Any]]) -> str:
    lines = [f"class {class_name}(BaseModel):"]
    for col in columns:
        name = col["column_name"]
        py_type = _map_type("python", col["data_type"])
        nullable = col.get("is_nullable") in (True, "YES")
        annotation = f"{py_type} | None" if nullable else py_type
        default = " = None" if nullable else ""
        lines.append(f"    {name}: {annotation}{default}")
    return "\n".join(lines) + "\n"


def _python_repository(
    class_name: str,
    table_full: str,
    pk: list[str],
    has_email: bool,
    async_mode: bool,
) -> str:
    pk_args = ", ".join(f"{col}: UUID" for col in pk) or "row_id: UUID"
    pk_filter = " AND ".join(f"{col} = ${i + 1}" for i, col in enumerate(pk)) or "id = $1"
    pk_call_args = ", ".join(pk) or "row_id"
    a = "async " if async_mode else ""
    aw = "await " if async_mode else ""

    methods = [
        f"    {a}def get_by_id(self, {pk_args}) -> {class_name} | None:",
        f"        row = {aw}self.conn.fetchrow(",
        f'            "SELECT * FROM {table_full} WHERE {pk_filter}",',
        f"            {pk_call_args},",
        "        )",
        f"        return {class_name}(**dict(row)) if row else None",
        "",
    ]
    if has_email:
        methods += [
            f"    {a}def get_by_email(self, email: str) -> {class_name} | None:",
            f"        row = {aw}self.conn.fetchrow(",
            f'            "SELECT * FROM {table_full} WHERE email = $1", email,',
            "        )",
            f"        return {class_name}(**dict(row)) if row else None",
            "",
        ]
    methods += [
        f"    {a}def list_paginated(self, limit: int = 50, offset: int = 0) -> list[{class_name}]:",
        f"        rows = {aw}self.conn.fetch(",
        f'            "SELECT * FROM {table_full} ORDER BY {pk[0] if pk else "1"} LIMIT $1 OFFSET $2",',
        "            limit, offset,",
        "        )",
        f"        return [{class_name}(**dict(r)) for r in rows]",
    ]

    return (
        f"class {class_name}Repository:\n"
        f"    def __init__(self, conn) -> None:\n"
        f"        self.conn = conn\n"
        "\n"
        + "\n".join(methods)
        + "\n"
    )


async def generate_repository_context_impl(
    db: Database,
    policy: ServerPolicy,
    schema: str,
    table: str,
    language: str = "python",
    async_mode: bool = True,
) -> dict[str, Any]:
    """Return scaffolding context for a repository class.

    The output is intentionally structured (separate ``model``, ``repository``,
    ``primary_key`` etc.) so an LLM can drop sections into a larger generated
    file without re-parsing free-form text.
    """
    language = language.lower()
    if language not in LANG_MAP:
        raise ValueError(
            f"Unsupported language: {language!r} (expected python, typescript, or java)"
        )

    metadata = await describe_table_impl(db, policy, schema, table)
    columns = metadata["columns"]
    primary_key = metadata.get("primary_key") or []
    foreign_keys = metadata.get("foreign_keys") or []
    table_full = f"{schema}.{table}"
    class_name = _camel_case(table)

    column_summaries = [
        {
            "name": c["column_name"],
            "sql_type": c["data_type"],
            "language_type": _map_type(language, c["data_type"]),
            "nullable": c.get("is_nullable") in (True, "YES"),
            "default": c.get("column_default"),
        }
        for c in columns
    ]

    has_email = any(c["column_name"] == "email" for c in columns)
    suggested_methods = ["get_by_id", "create", "update", "delete", "list_paginated"]
    if has_email:
        suggested_methods.insert(1, "get_by_email")

    if language == "python":
        model_code = _python_model(class_name, columns)
        repository_code = _python_repository(
            class_name, table_full, primary_key, has_email, async_mode
        )
    elif language == "typescript":
        field_lines = [
            f"  {c['name']}: "
            + (f"{c['language_type']} | null" if c["nullable"] else c["language_type"])
            + ";"
            for c in column_summaries
        ]
        model_code = f"export interface {class_name} {{\n" + "\n".join(field_lines) + "\n}\n"
        repository_code = (
            f"export class {class_name}Repository {{\n"
            "  constructor(private readonly db: Pool) {}\n"
            "  async getById(id: string) { /* ... */ }\n"
            "  async listPaginated(limit = 50, offset = 0) { /* ... */ }\n"
            "}\n"
        )
    else:  # java
        field_lines = [
            f"    private {c['language_type']} {c['name']};" for c in column_summaries
        ]
        model_code = (
            f"public class {class_name} {{\n" + "\n".join(field_lines) + "\n}\n"
        )
        repository_code = (
            f"public interface {class_name}Repository {{\n"
            f"    Optional<{class_name}> findById(UUID id);\n"
            f"    List<{class_name}> listPaginated(int limit, int offset);\n"
            "}\n"
        )

    return {
        "schema": schema,
        "table": table,
        "language": language,
        "async_mode": async_mode,
        "class_name": class_name,
        "primary_key": primary_key,
        "foreign_keys": foreign_keys,
        "columns": column_summaries,
        "suggested_methods": suggested_methods,
        "model": model_code,
        "repository": repository_code,
    }


def register_repository_tools(mcp: Any, db: Database, policy: ServerPolicy) -> None:
    @mcp.tool(name="postgres.generate_repository_context")
    async def generate_repository_context(
        schema: str,
        table: str,
        language: str = "python",
        async_mode: bool = True,
    ) -> dict[str, Any]:
        """Generate repository-pattern code scaffolding from a table schema.

        Returns a structured payload (model code, repository code, columns,
        primary key, foreign keys, suggested methods) that GitPilot's Coder
        agent feeds to the LLM as grounding context. Read-only.
        """
        return await generate_repository_context_impl(
            db, policy, schema, table, language=language, async_mode=async_mode
        )
