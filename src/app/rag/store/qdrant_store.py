"""Qdrant vector store: коллекция 384 dim (cosine), upsert/search/get/delete по doc_id."""
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.settings import Settings

VECTOR_SIZE = 384  # intfloat/multilingual-e5-small


class QdrantStore:
    """Обёртка над qdrant_client: коллекция kb_chunks_v1, cosine, payload с метаданными чанков."""

    def __init__(
        self,
        url: str | None = None,
        collection_name: str | None = None,
        client: QdrantClient | None = None,
    ):
        settings = Settings()
        self._client = client or QdrantClient(url or settings.qdrant_url)
        self._collection = collection_name or settings.qdrant_collection

    def ensure_collection(self) -> None:
        """Создать коллекцию kb_chunks_v1 (size=384, cosine), если не существует."""
        collections = self._client.get_collections().collections
        if any(c.name == self._collection for c in collections):
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

    def upsert(self, points: list[tuple[str, list[float], dict[str, Any]]]) -> None:
        """
        Добавить/обновить точки. Каждый элемент: (chunk_id, vector, payload).
        Payload: doc_id, doc_key, title, doc_type, language, chunk_id, chunk_index, section, text.
        """
        if not points:
            return
        self.ensure_collection()
        structs = [
            PointStruct(
                id=chunk_id,
                vector=vector,
                payload={
                    "doc_id": str(p.get("doc_id", "")),
                    "doc_key": str(p.get("doc_key", "")),
                    "title": str(p.get("title", "")),
                    "doc_type": str(p.get("doc_type", "")),
                    "language": str(p.get("language", "")),
                    "chunk_id": str(p.get("chunk_id", chunk_id)),
                    "chunk_index": int(p.get("chunk_index", 0)),
                    "section": str(p.get("section", "")),
                    "text": str(p.get("text", "")),
                },
            )
            for chunk_id, vector, p in points
        ]
        self._client.upsert(collection_name=self._collection, points=structs)

    def search(
        self,
        query_vector: list[float],
        k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """
        Поиск по вектору. Возвращает список (chunk_id, score, payload).
        filters: опционально doc_type, language (allowlist из policy).
        """
        self.ensure_collection()
        query_filter = None
        if filters:
            must = []
            if "doc_type" in filters and filters["doc_type"]:
                must.append(
                    FieldCondition(key="doc_type", match=MatchValue(value=filters["doc_type"]))
                )
            if "language" in filters and filters["language"]:
                must.append(
                    FieldCondition(key="language", match=MatchValue(value=filters["language"]))
                )
            if must:
                query_filter = Filter(must=must)
        response = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            limit=k,
            query_filter=query_filter,
        )
        return [
            (str(p.id), float(p.score), p.payload or {})
            for p in response.points
        ]

    def get_by_id(self, chunk_id: str) -> dict[str, Any] | None:
        """Получить точку по chunk_id: полный payload и вектор."""
        self.ensure_collection()
        points = self._client.retrieve(
            collection_name=self._collection,
            ids=[chunk_id],
            with_payload=True,
            with_vectors=True,
        )
        if not points:
            return None
        p = points[0]
        out = dict(p.payload or {})
        out["vector"] = p.vector if p.vector else []
        return out

    def delete_by_doc_id(self, doc_id: str) -> None:
        """Удалить все точки документа (для идемпотентного ingest при обновлении)."""
        doc_id_str = str(doc_id)
        self._client.delete(
            collection_name=self._collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(key="doc_id", match=MatchValue(value=doc_id_str)),
                    ]
                )
            ),
        )
