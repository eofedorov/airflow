"""Чтение и нормализация документов из папки."""
import json
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Нормализация текста: пробелы, переносы."""
    t = text.strip()
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _normalize_doc(d: dict[str, Any]) -> dict[str, Any] | None:
    """Приводит один документ к формату loader (doc_id, title, path, document_type, created_at, content)."""
    doc_id = d.get("doc_id") or d.get("doc_key") or ""
    title = d.get("title") or ""
    content = d.get("content") or ""
    if not doc_id or not content:
        return None
    path_val = d.get("path") or doc_id
    return {
        "doc_id": doc_id,
        "title": title,
        "path": path_val,
        "document_type": d.get("document_type") or d.get("doc_type") or "",
        "created_at": d.get("created_at") or "",
        "content": normalize_text(content),
    }


def _parse_json_docs(data: Any) -> list[dict[str, Any]]:
    """Извлечь и нормализовать документы из parsed JSON (list / {documents: [...]} / одиночный dict)."""
    out: list[dict[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                norm = _normalize_doc(item)
                if norm is not None:
                    out.append(norm)
    elif isinstance(data, dict):
        if "documents" in data:
            for d in data["documents"]:
                if isinstance(d, dict):
                    norm = _normalize_doc(d)
                    if norm is not None:
                        out.append(norm)
        else:
            norm = _normalize_doc(data)
            if norm is not None:
                out.append(norm)
    return out


def read_documents_from_folder(
    folder: Path,
    doc_key: str | None = None,
) -> list[dict[str, Any]]:
    """
    Читает документы из папки: glob *.json, парсинг одиночного объекта или массива documents,
    нормализация в формат loader.
    Если doc_key задан — возвращает только документ с этим doc_key (или пустой список).
    """
    if not folder.exists() or not folder.is_dir():
        return []

    out: list[dict[str, Any]] = []
    for f in sorted(folder.glob("*.json")):
        raw = f.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Skipping invalid JSON file: %s", f.name)
            continue
        out.extend(_parse_json_docs(data))

    if doc_key is not None:
        out = [d for d in out if d.get("doc_id") == doc_key]
    return out
