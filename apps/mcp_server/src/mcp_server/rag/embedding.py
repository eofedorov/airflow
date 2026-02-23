"""Общий синглтон модели эмбеддингов для RAG (retrieve + ingest)."""
from typing import Any

from mcp_server.settings import Settings

_settings = Settings()
_model: Any = None


def get_embedding_model() -> Any:
    """Возвращает единственный экземпляр SentenceTransformer в процессе."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_settings.rag_embedding_model)
    return _model
