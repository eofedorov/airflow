"""Точка входа FastAPI."""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from gateway.api.routes import router
from gateway.api import routes_rag
from gateway.mcp.client.mcp_client import MCPConnectionError, MCPToolError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logging.getLogger("gateway").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("mcp.client.streamable_http").setLevel(logging.WARNING)

app = FastAPI(title="LLM-Gate", description="AI-шлюз для инженерных задач")
app.include_router(router, prefix="", tags=["run"])
app.include_router(routes_rag.router, prefix="/rag", tags=["rag"])

_web_ui_dir = Path(__file__).resolve().parent.parent.parent / "web-ui"
if _web_ui_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_web_ui_dir), html=True), name="web-ui")


@app.exception_handler(MCPConnectionError)
def handle_mcp_connection_error(_request, exc: MCPConnectionError):
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
    )


@app.exception_handler(MCPToolError)
def handle_mcp_tool_error(_request, exc: MCPToolError):
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
    )
