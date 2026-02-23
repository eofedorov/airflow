"""Точка входа FastAPI."""
import json
import logging
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from datastore.docs import read_documents_from_folder
from datastore.schemas import DocumentIn
from datastore.settings import Settings

logging.getLogger("datastore").setLevel(logging.INFO)

app = FastAPI(title="Datastore", description="Хранилище документов для RAG (upload/read/delete)")


def _get_settings() -> Settings:
    return Settings()


def _source_folder(settings: Settings) -> Path:
    """Папка-источник: knowledge_base если не пуста, иначе demo."""
    kb = settings.knowledge_base_path
    if kb.exists() and any(kb.glob("*.json")):
        return kb
    return settings.demo_path


# ---- GET /read ----
@app.get("/read", response_model=None)
def read(
    doc_key: str | None = Query(None, description="Опционально: один документ по doc_key"),
):
    """Возвращает документы: из knowledge_base если не пуста, иначе из demo. Ответ всегда {"documents": [...]}."""
    settings = _get_settings()
    folder = _source_folder(settings)
    documents = read_documents_from_folder(folder, doc_key=doc_key)
    if doc_key is not None and not documents:
        raise HTTPException(status_code=404, detail=f"Документ с doc_key={doc_key!r} не найден")
    return JSONResponse(content={"documents": documents})


# ---- POST /upload ----
@app.post("/upload")
def upload(files: list[UploadFile] = File(...)):
    """
    Принимает только отдельные JSON-файлы (multipart). Каждый файл — один документ (doc_key, title, doc_type, content).
    Сохранение в knowledge_base как {doc_key}.json. При ошибке — 400 с описанием по файлам.
    """
    settings = _get_settings()
    kb = settings.knowledge_base_path
    kb.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    saved: list[str] = []
    for uf in files:
        filename = uf.filename or "<unnamed>"
        try:
            raw = uf.file.read().decode("utf-8")
        except Exception as e:
            errors.append(f"файл {filename}: не удалось прочитать ({e})")
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            errors.append(f"файл {filename}: не JSON ({e})")
            continue
        if not isinstance(data, dict):
            errors.append(f"файл {filename}: ожидается JSON-объект, получен {type(data).__name__}")
            continue
        try:
            doc = DocumentIn.model_validate(data)
        except Exception as e:
            errors.append(f"файл {filename}: {e}")
            continue
        path = kb / f"{doc.doc_key}.json"
        path.write_text(
            doc.model_dump_json(exclude_none=False, by_alias=False),
            encoding="utf-8",
        )
        saved.append(doc.doc_key)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    return {"uploaded": saved}


# ---- DELETE /delete ----
@app.delete("/delete")
def delete(
    doc_key: str | None = Query(None, description="Опционально: удалить только документ с этим doc_key"),
):
    """Удаляет документы только в knowledge_base: все или по doc_key. Папку demo не трогает."""
    settings = _get_settings()
    kb = settings.knowledge_base_path
    if not kb.exists():
        return {"deleted": []}
    if doc_key is not None:
        path = kb / f"{doc_key}.json"
        if path.exists():
            path.unlink()
            return {"deleted": [doc_key]}
        return {"deleted": []}
    deleted: list[str] = []
    for f in kb.glob("*.json"):
        deleted.append(f.stem)
        f.unlink()
    return {"deleted": deleted}


# ---- GET /health ----
@app.get("/health")
def health():
    """Healthcheck для compose."""
    return {"status": "ok"}
