"""
Golden set: один ingest из data/ (Postgres + Qdrant), затем вопросы из golden/questions*.json.
Для каждого ok-вопроса retrieval должен вернуть чанк из expected_doc_ids;
для каждого insufficient_context — при пустом retrieval ask возвращает insufficient_context.
"""
import json
from pathlib import Path

import pytest

from app.rag.ask_service import ask
from app.rag.ingest.indexer import run_ingestion
from app.rag.retrieve import retrieve
from app.rag.store.qdrant_store import QdrantStore
from app.settings import Settings

_TEST_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _TEST_DIR.parent.parent
GOLDEN_DIR = _TEST_DIR / "golden"
DATA_DIR = _PROJECT_ROOT / "data"


def _golden_question_files():
    """Все questions*.json в golden/."""
    return sorted(GOLDEN_DIR.glob("questions*.json"))


def _load_questions(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _needs_postgres_qdrant():
    """Пропустить тесты, требующие Postgres и Qdrant, если не настроены."""
    s = Settings()
    if not s.database_url or not s.qdrant_url:
        pytest.skip("database_url and qdrant_url required for golden retrieve (Postgres + Qdrant)")


@pytest.fixture(scope="module")
def store():
    """Один раз индексируем data/ в Postgres + Qdrant, возвращаем QdrantStore для retrieve."""
    _needs_postgres_qdrant()
    try:
        run_ingestion(kb_path=DATA_DIR)
    except Exception as e:
        err = str(e).lower()
        if "connect" in err or "10061" in err or "connection" in err or "refused" in err:
            pytest.skip("Postgres or Qdrant not available (connection refused)")
        raise
    return QdrantStore()


def test_golden_retrieve_ok_questions(store):
    """По всем questions*.json: каждый ok-вопрос даёт retrieval с чанком из expected_doc_ids."""
    golden_files = _golden_question_files()
    assert golden_files, "No golden/questions*.json found"

    failed = []
    for path in golden_files:
        questions = _load_questions(path)
        ok_cases = [q for q in questions if q.get("expected_status") == "ok"]
        assert len(ok_cases) >= 15, f"{path.name} must have at least 15 ok questions"
        for q in ok_cases:
            # раньше было k=5
            results = retrieve(q["question"], k=5, store=store)
            expected_ids = set(q.get("expected_doc_ids") or [])
            found_doc_ids = {m.get("doc_id") for _, _, m in results}
            if not expected_ids & found_doc_ids:
                failed.append((path.name, q["question"][:50], expected_ids, list(found_doc_ids)[:3]))

    assert not failed, f"Retrieve failed for {len(failed)} questions: {failed[:5]}"


def test_golden_ask_insufficient_context():
    """По всем questions*.json: каждый insufficient_context при пустом retrieval даёт status insufficient_context."""
    golden_files = _golden_question_files()
    assert golden_files, "No golden/questions*.json found"

    def empty_retrieve(_query, k=5, filters=None):
        return []

    for path in golden_files:
        questions = _load_questions(path)
        insufficient = [q for q in questions if q.get("expected_status") == "insufficient_context"]
        assert len(insufficient) >= 5, f"{path.name} must have at least 5 insufficient_context questions"
        for q in insufficient:
            contract = ask(q["question"], k=5, _retrieve=empty_retrieve)
            assert contract.status == "insufficient_context", (
                f"[{path.name}] Expected insufficient_context for: {q['question'][:50]}"
            )
            assert len(contract.sources) == 0
