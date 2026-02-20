"""Настройки mcp_server: RAG (эмбеддинги, чанки, kb_path)."""
from pathlib import Path

from common.settings import BaseAppSettings


class Settings(BaseAppSettings):
    """MCP-server-специфичные поля поверх базовых (database_url, qdrant_* из common)."""

    datastore_url: str = ""
    rag_embedding_model: str = ""
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 64
    rag_default_k: int = 5
    rag_relevance_threshold: float = 0.3
    kb_path: str = ""


def get_kb_path() -> Path:
    """Путь к базе знаний: из env или по умолчанию repo/data/docs."""
    s = Settings()
    if s.kb_path:
        return Path(s.kb_path)
    # Default: repo/data/docs (local); в Docker задавать KB_PATH=/app/data/docs
    repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    return repo_root / "data" / "docs"
