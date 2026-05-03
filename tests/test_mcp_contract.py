from mcp_postgre_server.config import Settings
from mcp_postgre_server.server import build_server


def test_server_builds() -> None:
    settings = Settings(
        POSTGRES_DSN="postgresql://user:pass@localhost:5432/db",
        POSTGRES_ALLOWED_SCHEMAS="public",
    )
    server = build_server(settings)
    assert server is not None


def test_server_has_state() -> None:
    settings = Settings(
        POSTGRES_DSN="postgresql://user:pass@localhost:5432/db",
        POSTGRES_ALLOWED_SCHEMAS="public",
    )
    server = build_server(settings)
    assert hasattr(server, "_mcp_postgre_state")
