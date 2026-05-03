import pytest

from mcp_postgre_server.config import Settings
from mcp_postgre_server.security.policies import ServerPolicy


def make_policy() -> ServerPolicy:
    settings = Settings(
        POSTGRES_DSN="postgresql://user:pass@localhost:5432/db",
        POSTGRES_ALLOWED_SCHEMAS="public,app",
    )
    return ServerPolicy(settings)


def test_schema_allowed() -> None:
    policy = make_policy()
    decision = policy.schema_allowed("public")
    assert decision.allowed is True


def test_schema_rejected() -> None:
    policy = make_policy()
    decision = policy.schema_allowed("secret")
    assert decision.allowed is False


def test_policy_validates_safe_query() -> None:
    policy = make_policy()
    result = policy.validate_query("select * from public.users")
    assert result.allowed is True


def test_policy_rejects_unsafe_query() -> None:
    policy = make_policy()
    result = policy.validate_query("truncate table public.users")
    assert result.allowed is False
