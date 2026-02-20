"""Настройки gateway: LLM, MCP, RAG (дефолтный k)."""
from common.settings import BaseAppSettings


class Settings(BaseAppSettings):
    """Gateway-специфичные поля поверх базовых (database_url, qdrant_* из common)."""

    llm_base_url: str = ""
    llm_model: str = ""
    llm_max_tokens: int = 0
    llm_timeout: int = 0
    llm_max_retries: int = 0
    enable_token_meter: bool = False
    rag_default_k: int = 5
    mcp_server_url: str = ""
    mcp_timeout: int = 600
