"""Retrieval: после индексации поиск возвращает релевантные чанки (QdrantStore)."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.rag.ingest.indexer import run_ingestion
from app.rag.retrieve import retrieve
from app.rag.store.qdrant_store import QdrantStore
from app.settings import Settings

_TEST_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _TEST_DIR.parent.parent
DATA_DIR = _PROJECT_ROOT / "data"


def test_retrieve_without_index_returns_empty():
    """При пустой коллекции retrieve возвращает пустой список."""
    store = MagicMock(spec=QdrantStore)
    store.ensure_collection.return_value = None
    store.search.return_value = []
    mock_model = MagicMock()
    mock_model.encode.return_value.tolist.return_value = [[0.0] * 384]
    with patch("app.rag.retrieve._model_singleton", return_value=mock_model):
        results = retrieve("Redis cache bypass", k=3, store=store)
    assert results == []
    store.ensure_collection.assert_called_once()
    store.search.assert_called_once()


@pytest.mark.slow
def test_retrieve_after_ingest_returns_chunks():
    """Индексация в Postgres+Qdrant → retrieve возвращает чанки. Требует database_url и qdrant_url."""
    s = Settings()
    if not s.database_url or not s.qdrant_url:
        pytest.skip("database_url and qdrant_url required")
    try:
        run_ingestion(kb_path=DATA_DIR)
    except Exception as e:
        if "connect" in str(e).lower() or "10061" in str(e) or "refused" in str(e).lower():
            pytest.skip("Postgres or Qdrant not available")
        raise
    store = QdrantStore()
    results = retrieve("Redis evictions cart staleness", k=3, store=store)
    assert len(results) > 0
    for chunk_id, score, meta in results:
        assert chunk_id
        assert "doc_id" in meta
        assert "title" in meta
        assert "text" in meta
