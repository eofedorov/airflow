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

from mcp_server.settings import Settings

VECTOR_SIZE = 384


class QdrantStore:
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
        collections = self._client.get_collections().collections
        if any(c.name == self._collection for c in collections):
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

    def upsert(self, points: list[tuple[str, list[float], dict[str, Any]]]) -> None:
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
        self.ensure_collection()
        query_filter = None
        if filters:
            must = []
            if filters.get("doc_type"):
                must.append(FieldCondition(key="doc_type", match=MatchValue(value=filters["doc_type"])))
            if filters.get("language"):
                must.append(FieldCondition(key="language", match=MatchValue(value=filters["language"])))
            if must:
                query_filter = Filter(must=must)
        response = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            limit=k,
            query_filter=query_filter,
        )
        return [(str(p.id), float(p.score), p.payload or {}) for p in response.points]

    def get_by_id(self, chunk_id: str) -> dict[str, Any] | None:
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
        doc_id_str = str(doc_id)
        self._client.delete(
            collection_name=self._collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id_str))],
                )
            ),
        )
