"""Точка входа MCP-сервера: Streamable HTTP на порту 8001."""
import uvicorn
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.mcp.server.app import mcp

# Регистрация инструментов при импорте
import app.mcp.server.tools  # noqa: F401


async def _health(_):
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    app = mcp.streamable_http_app()
    app.routes.insert(0, Route("/health", _health, methods=["GET"]))
    uvicorn.run(app, host="0.0.0.0", port=8001)
