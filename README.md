# MCP PostgreSQL Server

Production-ready PostgreSQL MCP server for code-generation agents such as GitPilot, orchestrated through MCP Context Forge.

This server exposes safe PostgreSQL schema, query, migration, explain-plan, and test-data capabilities through the Model Context Protocol (MCP). It is designed to be read-only by default and suitable for attaching to MCP Context Forge as a managed upstream MCP server.

## Features

- Streamable HTTP MCP endpoint at `/mcp`
- PostgreSQL connection pooling with `asyncpg`
- Read-only SQL guard by default
- Schema allowlist and row limits
- Safe SELECT execution
- Table, schema, index, constraint, and foreign-key discovery
- Migration validation without execution
- EXPLAIN support with production-safe defaults
- Deterministic test fixture generation
- MCP resources for schema and table metadata
- Docker and Compose support
- Pytest contract and security tests

## Security defaults

The server starts in a conservative mode:

```env
POSTGRES_READ_ONLY=true
POSTGRES_BLOCK_DDL=true
POSTGRES_BLOCK_DML=true
POSTGRES_MAX_ROWS=100
POSTGRES_QUERY_TIMEOUT_SECONDS=5
POSTGRES_ALLOWED_SCHEMAS=public
```

By default, the server allows safe read-only introspection and parameterized SELECT queries only. Destructive operations are blocked unless explicitly enabled.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Health endpoint:

```bash
curl http://localhost:8080/health
```

MCP endpoint:

```text
http://localhost:8080/mcp
```

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
python -m mcp_postgre_server.server
```

## Environment variables

| Variable | Default | Description |
|---|---:|---|
| `POSTGRES_DSN` | required | PostgreSQL DSN |
| `MCP_SERVER_HOST` | `0.0.0.0` | HTTP bind host |
| `MCP_SERVER_PORT` | `8080` | HTTP bind port |
| `MCP_MOUNT_PATH` | `/mcp` | MCP Streamable HTTP mount path |
| `MCP_AUTH_TOKEN` | empty | Optional bearer token expected from gateway |
| `POSTGRES_ALLOWED_SCHEMAS` | `public` | Comma-separated schema allowlist |
| `POSTGRES_READ_ONLY` | `true` | Enables read-only mode |
| `POSTGRES_BLOCK_DDL` | `true` | Blocks CREATE/ALTER/DROP/TRUNCATE/etc. |
| `POSTGRES_BLOCK_DML` | `true` | Blocks INSERT/UPDATE/DELETE/MERGE/CALL/etc. |
| `POSTGRES_MAX_ROWS` | `100` | Max returned rows for query tools |
| `POSTGRES_QUERY_TIMEOUT_SECONDS` | `5` | Statement timeout |
| `POSTGRES_POOL_MIN_SIZE` | `1` | Minimum pool size |
| `POSTGRES_POOL_MAX_SIZE` | `10` | Maximum pool size |
| `POSTGRES_EXPLAIN_ANALYZE_ALLOWED` | `false` | Allows `EXPLAIN ANALYZE` |

## Tools

| Tool | Purpose |
|---|---|
| `postgres_health` | Check DB connectivity and server policy |
| `postgres_list_schemas` | List allowed schemas |
| `postgres_list_tables` | List tables/views in a schema |
| `postgres_describe_table` | Describe columns, indexes, constraints, and FKs |
| `postgres_safe_select` | Execute one guarded read-only query |
| `postgres_explain_query` | Run `EXPLAIN` on a guarded query |
| `postgres_validate_migration` | Validate migration SQL against policy |
| `postgres_generate_test_fixtures` | Generate deterministic SQL insert fixtures |

## Resources

| Resource URI | Purpose |
|---|---|
| `postgres://schemas` | List available schemas |
| `postgres://schema/{schema}` | Schema metadata |
| `postgres://table/{schema}/{table}` | Table metadata |

## Context Forge registration

Edit `context-forge/register.json` and register this server in MCP Context Forge.

Example endpoint:

```text
http://mcp-postgre-server:8080/mcp
```

## Production recommendations

1. Run this service in a private network behind MCP Context Forge.
2. Use a PostgreSQL role with the minimum required privileges.
3. Keep `POSTGRES_READ_ONLY=true` unless a dedicated reviewed workflow needs writes.
4. Use schema allowlists.
5. Enable gateway authentication.
6. Log MCP tool calls at the gateway and service layer.
7. Use separate instances for dev, staging, and production databases.

## License

Apache-2.0

---
Used by [GitPilot](https://github.com/ruslanmv/gitpilot)'s MCP Context Forge stack ([`docker-compose.mcp.yml`](https://github.com/ruslanmv/gitpilot/blob/main/docker-compose.mcp.yml)). Image published via `.github/workflows/docker-publish.yml` on each release.
