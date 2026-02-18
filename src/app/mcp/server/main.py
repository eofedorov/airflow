"""Точка входа MCP-сервера: Streamable HTTP на порту 8001."""
from app.mcp.server.app import mcp

# Регистрация инструментов при импорте
import app.mcp.server.tools  # noqa: F401

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
