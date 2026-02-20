"""Pydantic-модели для валидации документов."""
from pydantic import BaseModel, Field


class DocumentIn(BaseModel):
    """Эталон документа для upload: один JSON-объект на файл."""

    doc_key: str = Field(..., min_length=1, description="Уникальный ключ документа")
    title: str = Field(..., description="Заголовок")
    doc_type: str = Field(..., description="Тип документа (adr, pm, …)")
    content: str = Field(..., min_length=1, description="Текстовое содержимое")
    created_at: str | None = None
    language: str | None = None
