"""Точка входа MCP-сервера: Streamable HTTP на порту 8001."""
import logging
import sys

import uvicorn
from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp_server.app import mcp

import mcp_server.tools  # noqa: F401


async def _health(_):
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    # Один раз настраиваем логирование, чтобы uvicorn не добавлял свои хендлеры и не дублировал строки.
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
    app = mcp.streamable_http_app()
    app.routes.insert(0, Route("/health", _health, methods=["GET"]))
    uvicorn.run(app, host="0.0.0.0", port=8001, log_config=None)
