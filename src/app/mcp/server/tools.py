"""Четыре MCP-инструмента: kb_search, kb_get_chunk, sql_read, kb_ingest."""
import re
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.db.connection import get_pool
from app.db.queries import execute_readonly_sql, get_sql_allowlist
from app.rag.formats import truncate_preview
from app.rag.ingest.indexer import run_ingestion
from app.rag.retrieve import retrieve
from app.rag.store.qdrant_store import QdrantStore

from app.mcp.server.app import mcp
from app.mcp.server.audit import log_tool_call as audit_log
from app.mcp.server.policy import (
    PolicyError,
    SQL_MAX_ROWS,
    validate_filters,
    validate_k,
    validate_query,
    validate_sql,
)

# Извлечение таблиц из SELECT: FROM schema.table или JOIN schema.table
_TABLE_REF = re.compile(
    r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)


def _check_sql_allowlist(conn, query: str) -> None:
    """Проверить, что все упомянутые таблицы входят в allowlist."""
    allowlist = set(get_sql_allowlist(conn))
    for m in _TABLE_REF.finditer(query):
        schema, table = m.group(1), m.group(2)
        if (schema, table) not in allowlist:
            raise PolicyError(f"Table {schema}.{table} is not in sql_allowlist")


def _serialize_cell(x: Any) -> Any:
    """Привести ячейку к JSON-сериализуемому типу."""
    if x is None:
        return None
    if isinstance(x, (datetime, date)):
        return x.isoformat()
    if isinstance(x, (UUID, Decimal)):
        return str(x)
    if isinstance(x, (str, int, float, bool)):
        return x
    return str(x)


@mcp.tool()
def kb_search(
    query: str,
    k: int = 5,
    filters: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """
    Поиск по базе знаний: семантический поиск по запросу.
    Возвращает chunks: [{id, score, doc_meta, preview}].
    """
    start = time.perf_counter()
    args = {"query": query, "k": k, "filters": filters}
    result_meta: dict[str, Any] = {}
    try:
        validate_query(query)
        validate_k(k)
        safe_filters = validate_filters(filters)
        chunks_raw = retrieve(query.strip(), k=k, filters=safe_filters or None)
        previews = [
            {
                "id": cid,
                "score": round(score, 4),
                "doc_meta": {
                    "doc_id": meta.get("doc_id"),
                    "title": meta.get("title"),
                    "doc_type": meta.get("doc_type"),
                    "project": meta.get("project"),
                },
                "preview": truncate_preview(meta.get("text", ""), 300),
            }
            for cid, score, meta in chunks_raw
        ]
        result_meta = {"chunk_count": len(previews)}
        duration_ms = int((time.perf_counter() - start) * 1000)
        audit_log(
            "kb_search",
            args=args,
            result_meta=result_meta,
            status="ok",
            duration_ms=duration_ms,
            run_id=run_id,
        )
        return {"chunks": previews}
    except PolicyError as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        audit_log(
            "kb_search",
            args=args,
            result_meta=result_meta,
            status="blocked",
            error_message=str(e),
            duration_ms=duration_ms,
            run_id=run_id,
        )
        raise
    except Exception as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        audit_log(
            "kb_search",
            args=args,
            result_meta=result_meta,
            status="error",
            error_message=str(e),
            duration_ms=duration_ms,
            run_id=run_id,
        )
        raise


@mcp.tool()
def kb_get_chunk(chunk_id: str, run_id: str | None = None) -> dict[str, Any]:
    """
    Получить полный текст и метаданные чанка по chunk_id.
    """
    start = time.perf_counter()
    args = {"chunk_id": chunk_id}
    result_meta: dict[str, Any] = {}
    try:
        if not chunk_id or not isinstance(chunk_id, str) or not chunk_id.strip():
            raise PolicyError("chunk_id is required and must be non-empty string")
        store = QdrantStore()
        data = store.get_by_id(chunk_id.strip())
        if data is None:
            result_meta = {"found": False}
            duration_ms = int((time.perf_counter() - start) * 1000)
            audit_log(
                "kb_get_chunk",
                args=args,
                result_meta=result_meta,
                status="ok",
                duration_ms=duration_ms,
                run_id=run_id,
            )
            return {"chunk_id": chunk_id, "text": "", "meta": {}, "found": False}
        vector = data.pop("vector", None)
        text = data.get("text", "")
        result_meta = {"found": True, "text_len": len(text)}
        duration_ms = int((time.perf_counter() - start) * 1000)
        audit_log(
            "kb_get_chunk",
            args=args,
            result_meta=result_meta,
            status="ok",
            duration_ms=duration_ms,
            run_id=run_id,
        )
        return {"chunk_id": chunk_id, "text": text, "meta": data, "found": True}
    except PolicyError as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        audit_log(
            "kb_get_chunk",
            args=args,
            result_meta=result_meta,
            status="blocked",
            error_message=str(e),
            duration_ms=duration_ms,
            run_id=run_id,
        )
        raise
    except Exception as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        audit_log(
            "kb_get_chunk",
            args=args,
            result_meta=result_meta,
            status="error",
            error_message=str(e),
            duration_ms=duration_ms,
            run_id=run_id,
        )
        raise


@mcp.tool()
def sql_read(query: str, run_id: str | None = None) -> dict[str, Any]:
    """
    Выполнить только SELECT по разрешённым таблицам (allowlist). Максимум 200 строк.
    Возвращает columns, rows, row_count.
    """
    start = time.perf_counter()
    args = {"query": query}
    result_meta: dict[str, Any] = {}
    try:
        validate_sql(query)
        pool = get_pool()
        with pool.connection() as conn:
            _check_sql_allowlist(conn, query)
            columns, rows, row_count = execute_readonly_sql(conn, query, limit=SQL_MAX_ROWS)
        rows = [[_serialize_cell(x) for x in row] for row in rows]
        result_meta = {"row_count": row_count, "column_count": len(columns)}
        duration_ms = int((time.perf_counter() - start) * 1000)
        audit_log(
            "sql_read",
            args=args,
            result_meta=result_meta,
            status="ok",
            duration_ms=duration_ms,
            run_id=run_id,
        )
        return {"columns": columns, "rows": rows, "row_count": row_count}
    except PolicyError as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        audit_log(
            "sql_read",
            args=args,
            result_meta=result_meta,
            status="blocked",
            error_message=str(e),
            duration_ms=duration_ms,
            run_id=run_id,
        )
        raise
    except Exception as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        audit_log(
            "sql_read",
            args=args,
            result_meta=result_meta,
            status="error",
            error_message=str(e),
            duration_ms=duration_ms,
            run_id=run_id,
        )
        raise


@mcp.tool()
def kb_ingest(run_id: str | None = None) -> dict[str, Any]:
    """
    Запустить индексацию базы знаний: загрузка документов -> чанкинг -> эмбеддинги -> Qdrant.
    Возвращает docs_indexed, chunks_indexed, duration_ms.
    """
    start = time.perf_counter()
    args: dict[str, Any] = {}
    result_meta: dict[str, Any] = {}
    try:
        result = run_ingestion()
        result_meta = result
        duration_ms = int((time.perf_counter() - start) * 1000)
        audit_log(
            "kb_ingest",
            args=args,
            result_meta=result_meta,
            status="ok",
            duration_ms=duration_ms,
            run_id=run_id,
        )
        return result
    except Exception as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        audit_log(
            "kb_ingest",
            args=args,
            result_meta=result_meta,
            status="error",
            error_message=str(e),
            duration_ms=duration_ms,
            run_id=run_id,
        )
        raise
