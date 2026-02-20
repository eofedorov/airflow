"""Retrieval: запрос -> эмбеддинг -> top-k чанков в Qdrant."""
import logging
from typing import Any

from mcp_server.rag.store.qdrant_store import QdrantStore
from mcp_server.settings import Settings

log = logging.getLogger(__name__)
_settings = Settings()
_model = None


def _get_embedding_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(_settings.rag_embedding_model)


def _model_singleton():
    global _model
    if _model is None:
        _model = _get_embedding_model()
    return _model


def retrieve(
    query: str,
    k: int | None = None,
    filters: dict[str, Any] | None = None,
    store: QdrantStore | None = None,
) -> list[tuple[str, float, dict[str, Any]]]:
    if not query or not query.strip():
        log.info("[RAG] retrieve empty query -> []")
        return []
    k_val = k if k is not None else _settings.rag_default_k
    log.info("[RAG] retrieve query=%r k=%s", query.strip()[:60], k_val)
    s = store if store is not None else QdrantStore()
    s.ensure_collection()
    model = _model_singleton()
    qv = model.encode([query.strip()], show_progress_bar=False).tolist()[0]
    results = s.search(qv, k=k_val, filters=filters)
    log.info("[RAG] retrieve done chunks=%d", len(results))
    return results
