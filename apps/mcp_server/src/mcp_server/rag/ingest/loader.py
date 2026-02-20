"""Загрузка документов из директории базы знаний или из datastore (GET /read)."""
import json
import logging
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from mcp_server.rag.formats import normalize_text
from mcp_server.settings import get_kb_path, Settings

log = logging.getLogger(__name__)


def _normalize_doc(d: dict[str, Any]) -> dict[str, Any] | None:
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


def _load_from_disk() -> list[dict[str, Any]]:
    p = get_kb_path()
    if not p.exists():
        log.error("Knowledge base path does not exist: %s", p)
        raise FileNotFoundError(f"Knowledge base path does not exist: {p}")
    if not p.is_dir():
        log.error("Knowledge base path is not a directory: %s", p)
        raise NotADirectoryError(f"Knowledge base path is not a directory: {p}")

    json_files = sorted(p.glob("*.json"))
    if not json_files:
        log.error("Knowledge base directory is empty (no *.json): %s", p)
        raise FileNotFoundError(f"Knowledge base directory is empty (no *.json): {p}")

    out: list[dict[str, Any]] = []
    for f in json_files:
        raw = f.read_text(encoding="utf-8")
        data = json.loads(raw)
        docs = data.get("documents") or []
        for d in docs:
            norm = _normalize_doc(d)
            if norm:
                out.append(norm)
    return out


def _load_from_datastore(datastore_url: str) -> list[dict[str, Any]]:
    url = datastore_url.rstrip("/") + "/read"
    with urlopen(url, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    docs = data.get("documents") if isinstance(data, dict) else data
    if not isinstance(docs, list):
        docs = []
    out: list[dict[str, Any]] = []
    for d in docs:
        norm = _normalize_doc(d)
        if norm:
            out.append(norm)
    return out


def load_documents() -> list[dict[str, Any]]:
    s = Settings()
    if s.datastore_url:
        return _load_from_datastore(s.datastore_url)
    return _load_from_disk()
