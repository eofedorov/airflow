"""Индексация: загрузка документов -> проверка sha256 (идемпотентность) -> Postgres -> чанкинг -> эмбеддинги -> Qdrant."""
import hashlib
import time
from pathlib import Path

from app.db.connection import get_pool
from app.db.queries import (
    delete_chunks_by_doc_id,
    get_document_by_doc_key,
    insert_chunk,
    insert_document,
    update_document_sha256,
)
from app.rag.ingest.chunker import chunk_document
from app.rag.ingest.loader import load_documents
from app.rag.store.qdrant_store import QdrantStore
from app.settings import Settings

_settings = Settings()


def _sha256_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _get_embedding_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(_settings.rag_embedding_model)


def run_ingestion(
    kb_path: Path | str | None = None,
    index_dir: Path | str | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> dict[str, int | float]:
    """
    Загрузить базу знаний -> по sha256 пропустить неизменённые -> Postgres (documents + chunks)
    -> эмбеддинги -> upsert в Qdrant. При обновлении документа старые точки в Qdrant удаляются.
    Возвращает { docs_indexed, chunks_indexed, duration_ms }.
    """
    start = time.perf_counter()
    cs = chunk_size if chunk_size is not None else _settings.rag_chunk_size
    ov = overlap if overlap is not None else _settings.rag_chunk_overlap
    docs = load_documents(kb_path)
    if not docs:
        return {"docs_indexed": 0, "chunks_indexed": 0, "duration_ms": 0.0}

    store = QdrantStore()
    store.ensure_collection()
    model = _get_embedding_model()
    docs_indexed = 0
    chunks_indexed = 0
    pool = get_pool()

    with pool.connection() as conn:
        for doc in docs:
            doc_key = doc.get("path") or doc.get("doc_id") or ""
            content = doc.get("content") or ""
            if not doc_key:
                continue
            new_sha = _sha256_content(content)
            existing = get_document_by_doc_key(conn, doc_key)
            if existing is not None:
                doc_id, existing_sha = existing
                if existing_sha == new_sha:
                    continue
                update_document_sha256(conn, doc_id, new_sha)
                delete_chunks_by_doc_id(conn, doc_id)
                store.delete_by_doc_id(str(doc_id))
            else:
                doc_id = insert_document(
                    conn,
                    doc_key=doc_key,
                    title=doc.get("title") or "",
                    doc_type=doc.get("document_type") or "general",
                    project="core",
                    language="ru",
                    sha256=new_sha,
                    source="local_fs",
                )
            docs_indexed += 1
            chunks = chunk_document(doc, chunk_size=cs, overlap=ov)
            if not chunks:
                continue
            texts = [c.text for c in chunks]
            vectors = model.encode(texts, show_progress_bar=False).tolist()
            title = doc.get("title") or ""
            doc_type = doc.get("document_type") or "general"
            points: list[tuple[str, list[float], dict]] = []
            for chunk, vec in zip(chunks, vectors):
                chunk_id_uuid = insert_chunk(
                    conn,
                    doc_id=doc_id,
                    chunk_index=chunk.chunk_index,
                    section=chunk.section or None,
                    text=chunk.text,
                    embedding_ref=None,
                )
                payload = {
                    "doc_id": str(doc_id),
                    "doc_key": doc_key,
                    "title": title,
                    "doc_type": doc_type,
                    "project": "core",
                    "language": "ru",
                    "chunk_id": str(chunk_id_uuid),
                    "chunk_index": chunk.chunk_index,
                    "section": chunk.section or "",
                    "text": chunk.text,
                }
                points.append((str(chunk_id_uuid), vec, payload))
            store.upsert(points)
            chunks_indexed += len(points)

    elapsed_ms = (time.perf_counter() - start) * 1000
    return {
        "docs_indexed": docs_indexed,
        "chunks_indexed": chunks_indexed,
        "duration_ms": round(elapsed_ms, 2),
    }
