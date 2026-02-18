"""
Фаза 5: перенос данных из FAISS в Qdrant + Postgres.

1. Загрузить FAISS-индекс + metadata.json из data/faiss_index/
2. Извлечь все векторы через reconstruct
3. Для каждого вектора + метаданные: записать документ/чанк в Postgres, upsert в Qdrant
4. Проверка: count в Qdrant == count в FAISS

Запуск из корня проекта: python -m tools.migrate_faiss_to_qdrant
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Корень проекта: tools/migrate_faiss_to_qdrant.py -> parent
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from app.db.connection import get_pool
from app.db.queries import get_document_by_doc_key, insert_chunk, insert_document
from app.rag.store.faiss_store import DEFAULT_INDEX_DIR, INDEX_FILE, METADATA_FILE
from app.rag.store.qdrant_store import QdrantStore
from app.settings import Settings


def _load_faiss_index(index_dir: Path):
    import faiss

    path = index_dir / INDEX_FILE
    meta_path = index_dir / METADATA_FILE
    if not path.exists():
        raise FileNotFoundError(f"FAISS index not found: {path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"Metadata not found: {meta_path}")

    index = faiss.read_index(str(path))
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    if index.ntotal != len(metadata):
        raise ValueError(
            f"FAISS index count ({index.ntotal}) != metadata length ({len(metadata)})"
        )
    return index, metadata


def _reconstruct_vectors(index) -> np.ndarray:
    """Извлечь все векторы из FAISS-индекса (порядок совпадает с id 0..ntotal-1)."""
    return index.reconstruct_n(0, index.ntotal)


def _doc_key(meta: dict[str, Any]) -> str:
    """Уникальный ключ документа для группировки и llm.kb_documents.doc_key."""
    return (meta.get("path") or meta.get("doc_id") or "").strip() or str(meta.get("doc_id", ""))


def run_migration(
    index_dir: Path | None = None,
    skip_existing_docs: bool = True,
) -> dict[str, Any]:
    """
    Выполнить миграцию FAISS -> Postgres + Qdrant.

    skip_existing_docs: если True, не вставлять документ, если doc_key уже есть (по одному doc_key из метаданных).
    """
    settings = Settings()
    index_dir = index_dir or Path(settings.rag_index_dir or DEFAULT_INDEX_DIR)
    if not index_dir.is_absolute():
        index_dir = _PROJECT_ROOT / index_dir

    index, metadata = _load_faiss_index(index_dir)
    vectors = _reconstruct_vectors(index)

    store = QdrantStore()
    store.ensure_collection()
    pool = get_pool()

    # Группировка по документу: doc_key -> { title, doc_type, list of (idx, meta) }
    doc_groups: dict[str, dict[str, Any]] = {}
    for idx, meta in enumerate(metadata):
        key = _doc_key(meta)
        if key not in doc_groups:
            doc_groups[key] = {
                "title": meta.get("title") or "",
                "doc_type": meta.get("document_type") or "general",
                "chunks": [],
            }
        doc_groups[key]["chunks"].append((idx, meta))

    # doc_key -> new doc_id (UUID)
    doc_key_to_id: dict[str, Any] = {}

    with pool.connection() as conn:
        for doc_key, group in doc_groups.items():
            if not doc_key:
                continue
            existing = get_document_by_doc_key(conn, doc_key) if skip_existing_docs else None
            if existing is not None:
                doc_key_to_id[doc_key] = existing[0]
            else:
                new_doc_id = insert_document(
                    conn,
                    doc_key=doc_key,
                    title=group["title"],
                    doc_type=group["doc_type"],
                    project="core",
                    language="ru",
                    source="local_fs",
                    sha256=None,
                )
                doc_key_to_id[doc_key] = new_doc_id

        points: list[tuple[str, list[float], dict[str, Any]]] = []
        for doc_key, group in doc_groups.items():
            if not doc_key:
                continue
            doc_id = doc_key_to_id.get(doc_key)
            if doc_id is None:
                continue
            title = group["title"]
            doc_type = group["doc_type"]
            # Сортируем по chunk_index для консистентности
            chunks_sorted = sorted(group["chunks"], key=lambda x: x[1].get("chunk_index", 0))
            for idx, meta in chunks_sorted:
                vec = vectors[idx].tolist()
                chunk_index = int(meta.get("chunk_index", 0))
                section = meta.get("section") or ""
                text = meta.get("text") or ""

                new_chunk_id = insert_chunk(
                    conn,
                    doc_id=doc_id,
                    chunk_index=chunk_index,
                    section=section or None,
                    text=text,
                    text_tokens_est=0,
                    embedding_ref=None,
                )
                payload = {
                    "doc_id": str(doc_id),
                    "doc_key": doc_key,
                    "title": title,
                    "doc_type": doc_type,
                    "project": "core",
                    "language": "ru",
                    "chunk_id": str(new_chunk_id),
                    "chunk_index": chunk_index,
                    "section": section,
                    "text": text,
                }
                points.append((str(new_chunk_id), vec, payload))

        if points:
            store.upsert(points)

    # Проверка
    from qdrant_client import QdrantClient
    client = QdrantClient(settings.qdrant_url)
    info = client.get_collection(settings.qdrant_collection)
    qdrant_count = info.points_count
    faiss_count = index.ntotal

    return {
        "docs_migrated": len(doc_key_to_id),
        "chunks_migrated": len(points),
        "faiss_count": faiss_count,
        "qdrant_count": qdrant_count,
        "match": qdrant_count == faiss_count,
    }


def main() -> int:
    try:
        result = run_migration()
        print("Migration result:", result)
        return 0 if result["match"] else 1
    except Exception as e:
        print("Migration failed:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
