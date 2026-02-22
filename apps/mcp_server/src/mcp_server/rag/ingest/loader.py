"""Загрузка документов из datastore (GET /read)."""
import json
import logging
from typing import Any
from urllib.request import urlopen

from mcp_server.rag.formats import normalize_text
from mcp_server.settings import Settings

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


def load_documents() -> list[dict[str, Any]]:
    """Загрузить документы из datastore (GET /read). Требуется DATASTORE_URL."""
    s = Settings()
    if not s.datastore_url:
        raise RuntimeError(
            "DATASTORE_URL is not set. "
            "MCP server requires a running datastore to load documents for ingestion."
        )
    url = s.datastore_url.rstrip("/") + "/read"
    log.info("[LOADER] fetching documents from datastore: %s", url)
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
    log.info("[LOADER] loaded %d documents from datastore", len(out))
    return out
