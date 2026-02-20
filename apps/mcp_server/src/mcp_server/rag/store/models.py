"""Pydantic-модели для чанков. Формат chunk_id: doc:{doc_id}#chunk:{chunk_index}."""
from pydantic import BaseModel, ConfigDict


class DocumentMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc_id: str
    title: str
    path: str = ""
    document_type: str = ""
    created_at: str = ""
    section: str = ""


class ChunkMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str
    doc_id: str
    title: str
    path: str = ""
    document_type: str = ""
    created_at: str = ""
    section: str = ""
    chunk_index: int = 0
    text: str = ""


def make_chunk_id(doc_id: str, chunk_index: int) -> str:
    return f"doc:{doc_id}#chunk:{chunk_index}"
