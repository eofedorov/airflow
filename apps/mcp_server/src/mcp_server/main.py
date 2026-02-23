"""Точка входа MCP-сервера: Streamable HTTP на порту 8001."""
from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp_server.app import mcp

import mcp_server.tools  # noqa: F401


async def _health(_):
    return JSONResponse({"status": "ok"})


app = mcp.streamable_http_app()
app.routes.insert(0, Route("/health", _health, methods=["GET"]))
