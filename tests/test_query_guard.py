from mcp_postgre_server.security.sql_guard import validate_sql

DEFAULT = {
    "allowed_schemas": ["public"],
    "read_only": True,
    "block_ddl": True,
    "block_dml": True,
}


def test_allows_basic_select() -> None:
    result = validate_sql("select id, name from public.users", **DEFAULT)
    assert result.allowed is True
    assert result.normalized_sql


def test_blocks_delete() -> None:
    result = validate_sql("delete from public.users where id = 1", **DEFAULT)
    assert result.allowed is False
    assert "DML" in result.reason or "Read-only" in result.reason


def test_blocks_drop() -> None:
    result = validate_sql("drop table public.users", **DEFAULT)
    assert result.allowed is False


def test_blocks_multiple_statements() -> None:
    result = validate_sql("select 1; select 2", **DEFAULT)
    assert result.allowed is False
    assert "Multiple" in result.reason or "Exactly one" in result.reason


def test_blocks_disallowed_schema() -> None:
    result = validate_sql("select * from private.users", **DEFAULT)
    assert result.allowed is False
    assert "Schemas not allowed" in result.reason


def test_blocks_sleep() -> None:
    result = validate_sql("select pg_sleep(10)", **DEFAULT)
    assert result.allowed is False
