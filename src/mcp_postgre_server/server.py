from __future__ import annotations

import contextlib
import logging
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover
    from fastmcp import FastMCP  # type: ignore[no-redef]

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from mcp_postgre_server import __version__
from mcp_postgre_server.config import Settings, get_settings
from mcp_postgre_server.db import Database
from mcp_postgre_server.resources.database_resources import register_database_resources
from mcp_postgre_server.security.policies import ServerPolicy
from mcp_postgre_server.tools.explain import register_explain_tools
from mcp_postgre_server.tools.migrations import register_migration_tools
from mcp_postgre_server.tools.query import register_query_tools
from mcp_postgre_server.tools.schema import register_schema_tools
from mcp_postgre_server.tools.test_data import register_test_data_tools

logger = logging.getLogger(__name__)


class AppState:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = Database(settings)
        self.policy = ServerPolicy(settings)


def build_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or get_settings()
    state = AppState(settings)

    mcp = FastMCP(
        name=settings.server_name,
        instructions=(
            "Production PostgreSQL MCP server. Use schema discovery, safe read-only SELECT, "
            "EXPLAIN, migration validation, and test fixture tools. Mutation tools are not exposed."
        ),
        stateless_http=True,
        json_response=True,
    )

    # When mounted under /mcp in Starlette, serve MCP at that exact path rather than /mcp/mcp.
    mcp.settings.streamable_http_path = "/"

    register_schema_tools(mcp, state.db, state.policy)
    register_query_tools(mcp, state.db, state.policy)
    register_explain_tools(mcp, state.db, state.policy)
    register_migration_tools(mcp, state.policy)
    register_test_data_tools(mcp, state.db, state.policy)
    register_database_resources(mcp, state.db, state.policy)

    @mcp.tool(name="postgres_server_info")
    async def postgres_server_info() -> dict[str, Any]:
        """Return MCP PostgreSQL server information and active safety policy."""
        return {
            "name": settings.server_name,
            "version": __version__,
            "mount_path": settings.mount_path,
            "read_only": settings.read_only,
            "block_ddl": settings.block_ddl,
            "block_dml": settings.block_dml,
            "allowed_schemas": settings.allowed_schemas,
            "max_rows": settings.max_rows,
            "query_timeout_seconds": settings.query_timeout_seconds,
        }

    # Attach state for Starlette lifespan, health checks, tests, and advanced integrations.
    setattr(mcp, "_mcp_postgre_state", state)
    return mcp


def build_app(settings: Settings | None = None) -> Starlette:
    settings = settings or get_settings()
    mcp = build_server(settings)
    state: AppState = getattr(mcp, "_mcp_postgre_state")

    async def health(_: Request) -> Response:
        return JSONResponse(
            {
                "status": "ok",
                "server": settings.server_name,
                "version": __version__,
                "capabilities": {"tools": True, "resources": True, "prompts": False},
            }
        )

    async def ready(_: Request) -> Response:
        try:
            await state.db.connect()
            db_ok = await state.db.ping()
            status = "ready" if db_ok else "not_ready"
            code = 200 if db_ok else 503
        except Exception as exc:  # noqa: BLE001
            logger.exception("readiness check failed")
            return JSONResponse({"status": "not_ready", "error": str(exc)}, status_code=503)
        return JSONResponse({"status": status, "database": db_ok}, status_code=code)

    @contextlib.asynccontextmanager
    async def lifespan(_: Starlette):
        logging.basicConfig(level=settings.log_level.upper())
        await state.db.connect()
        async with mcp.session_manager.run():
            logger.info("started %s version=%s", settings.server_name, __version__)
            yield
        await state.db.close()
        logger.info("stopped %s", settings.server_name)

    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/ready", ready, methods=["GET"]),
            Mount(settings.mount_path, app=mcp.streamable_http_app()),
        ],
        lifespan=lifespan,
    )


def main() -> None:
    settings = get_settings()
    app = build_app(settings)
    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
