"""
Заполнение Qdrant эмбеддингами из существующих чанков в Postgres.

Берёт все чанки из llm.kb_chunks + llm.kb_documents,
вычисляет эмбеддинги через sentence-transformers,
upsert в Qdrant (коллекция kb_chunks_v1).

Запуск из корня проекта: python -m tools.seed_qdrant_from_postgres
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from app.db.connection import get_pool
from app.rag.store.qdrant_store import QdrantStore
from app.settings import Settings


def run_seed() -> dict:
    settings = Settings()
    pool = get_pool()
    store = QdrantStore()
    store.ensure_collection()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            rows = cur.execute("""
                SELECT c.chunk_id, c.doc_id, c.chunk_index, c.section, c.text,
                       d.doc_key, d.title, d.doc_type, d.project, d.language
                FROM llm.kb_chunks c
                JOIN llm.kb_documents d ON d.doc_id = c.doc_id
                WHERE d.is_active = TRUE
                ORDER BY d.doc_key, c.chunk_index
            """).fetchall()

    if not rows:
        print("No chunks found in Postgres.")
        return {"chunks": 0, "qdrant_points": 0}

    print(f"Found {len(rows)} chunks in Postgres. Computing embeddings...")

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(settings.rag_embedding_model)

    texts = [row[4] for row in rows]  # c.text
    vectors = model.encode(texts, show_progress_bar=True).tolist()

    points = []
    for row, vec in zip(rows, vectors):
        chunk_id, doc_id, chunk_index, section, text, doc_key, title, doc_type, project, language = row
        payload = {
            "doc_id": str(doc_id),
            "doc_key": doc_key,
            "title": title,
            "doc_type": doc_type,
            "project": project,
            "language": language,
            "chunk_id": str(chunk_id),
            "chunk_index": chunk_index,
            "section": section or "",
            "text": text,
        }
        points.append((str(chunk_id), vec, payload))

    print(f"Upserting {len(points)} points into Qdrant...")
    store.upsert(points)

    from qdrant_client import QdrantClient
    client = QdrantClient(settings.qdrant_url)
    info = client.get_collection(settings.qdrant_collection)

    result = {
        "chunks": len(rows),
        "qdrant_points": info.points_count,
        "match": info.points_count == len(rows),
    }
    print(f"Done: {result}")
    return result


def main() -> int:
    try:
        result = run_seed()
        return 0 if result.get("match") else 1
    except Exception as e:
        print(f"Seed failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
