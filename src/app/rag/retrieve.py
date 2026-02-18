"""Retrieval: запрос -> эмбеддинг -> top-k чанков в Qdrant с score и метаданными."""
from typing import Any

from app.rag.store.qdrant_store import QdrantStore
from app.settings import Settings

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
    """
    Энкодировать запрос, поиск в Qdrant, вернуть список (chunk_id, score, meta).
    meta содержит doc_id, doc_key, title, doc_type, project, language, chunk_index, section, text.
    """
    if not query or not query.strip():
        return []
    k_val = k if k is not None else _settings.rag_default_k
    s = store if store is not None else QdrantStore()
    s.ensure_collection()
    model = _model_singleton()
    qv = model.encode([query.strip()], show_progress_bar=False).tolist()[0]
    return s.search(qv, k=k_val, filters=filters)
