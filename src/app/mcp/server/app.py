"""Экземпляр FastMCP для регистрации tools (импортируется из main и tools)."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("LLM-Gate Tools", json_response=True)
