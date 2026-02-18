"""MCP tools: kb_search, kb_get_chunk, sql_read, kb_ingest — валидация и поведение с моками."""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from app.mcp.server.policy import PolicyError
from app.mcp.server.tools import kb_get_chunk, kb_ingest, kb_search, sql_read


def test_kb_search_valid_query_returns_chunks():
    """kb_search с валидным query возвращает список чанков."""
    fake_chunks = [
        ("chunk-uuid-1", 0.92, {
            "doc_id": "doc1", "title": "Doc 1", "doc_type": "runbook",
            "project": "core", "text": "Redis eviction policy.",
        }),
    ]
    with patch("app.mcp.server.tools.retrieve", return_value=fake_chunks):
        result = kb_search("Redis cache", k=5)
    assert "chunks" in result
    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["id"] == "chunk-uuid-1"
    assert result["chunks"][0]["score"] == 0.92
    assert "doc_meta" in result["chunks"][0]
    assert "preview" in result["chunks"][0]


def test_kb_search_k_over_10_raises():
    """kb_search с k > 10 -> PolicyError."""
    with pytest.raises(PolicyError) as exc_info:
        kb_search("query", k=11)
    assert "10" in str(exc_info.value)


def test_kb_search_empty_query_raises():
    """kb_search с пустым query -> PolicyError."""
    with pytest.raises(PolicyError):
        kb_search("", k=5)


def test_kb_get_chunk_found_returns_text_and_meta():
    """kb_get_chunk с существующим chunk_id возвращает полный текст и meta."""
    payload = {
        "text": "Full chunk text here.",
        "doc_id": "doc1", "title": "Doc 1", "doc_type": "runbook",
        "chunk_index": 0, "section": "",
    }
    with patch("app.mcp.server.tools.QdrantStore") as StoreMock:
        store_instance = MagicMock()
        store_instance.get_by_id.return_value = {**payload, "vector": [0.1] * 384}
        StoreMock.return_value = store_instance

        result = kb_get_chunk("chunk-uuid-1")

    assert result["found"] is True
    assert result["text"] == "Full chunk text here."
    assert result["chunk_id"] == "chunk-uuid-1"
    assert "meta" in result


def test_kb_get_chunk_not_found_returns_found_false():
    """kb_get_chunk при отсутствии чанка возвращает found: False."""
    with patch("app.mcp.server.tools.QdrantStore") as StoreMock:
        store_instance = MagicMock()
        store_instance.get_by_id.return_value = None
        StoreMock.return_value = store_instance

        result = kb_get_chunk("non-existent-id")

    assert result["found"] is False
    assert result["text"] == ""
    assert result["meta"] == {}


def test_kb_get_chunk_empty_id_raises():
    """kb_get_chunk с пустым chunk_id -> PolicyError."""
    with pytest.raises(PolicyError):
        kb_get_chunk("")
    with pytest.raises(PolicyError):
        kb_get_chunk("   ")


def test_sql_read_valid_select_returns_columns_rows():
    """sql_read с валидным SELECT возвращает columns, rows, row_count."""
    mock_conn = MagicMock()
    mock_allowlist = [("llm", "kb_documents"), ("llm", "kb_chunks")]

    @contextmanager
    def conn_ctx():
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.connection.side_effect = conn_ctx

    with (
        patch("app.mcp.server.tools.get_pool", return_value=mock_pool),
        patch("app.mcp.server.tools.get_sql_allowlist", return_value=mock_allowlist),
        patch("app.mcp.server.tools.execute_readonly_sql", return_value=(
            ["doc_id", "title"],
            [["id-1", "Doc 1"], ["id-2", "Doc 2"]],
            2,
        )),
    ):
        result = sql_read("SELECT doc_id, title FROM llm.kb_documents LIMIT 10")

    assert result["columns"] == ["doc_id", "title"]
    assert len(result["rows"]) == 2
    assert result["row_count"] == 2


def test_sql_read_forbidden_sql_raises():
    """sql_read с неразрешённым SQL -> PolicyError (до вызова БД)."""
    with pytest.raises(PolicyError):
        sql_read("DELETE FROM llm.kb_documents")


def test_sql_read_max_rows_enforcement():
    """execute_readonly_sql вызывается с limit=200."""
    mock_conn = MagicMock()
    mock_allowlist = [("llm", "kb_documents")]

    @contextmanager
    def conn_ctx():
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.connection.side_effect = conn_ctx

    with (
        patch("app.mcp.server.tools.get_pool", return_value=mock_pool),
        patch("app.mcp.server.tools.get_sql_allowlist", return_value=mock_allowlist),
        patch("app.mcp.server.tools.execute_readonly_sql") as exec_mock,
    ):
        exec_mock.return_value = (["x"], [], 0)
        sql_read("SELECT * FROM llm.kb_documents LIMIT 10")

    exec_mock.assert_called_once()
    call_kw = exec_mock.call_args[1]
    assert call_kw.get("limit") == 200


def test_kb_ingest_returns_stats():
    """kb_ingest возвращает docs_indexed, chunks_indexed, duration_ms."""
    with patch("app.mcp.server.tools.run_ingestion", return_value={
        "docs_indexed": 2,
        "chunks_indexed": 15,
        "duration_ms": 120.5,
    }):
        result = kb_ingest()

    assert result["docs_indexed"] == 2
    assert result["chunks_indexed"] == 15
    assert result["duration_ms"] == 120.5
