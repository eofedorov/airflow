"""Политика SQL: только SELECT, запрет опасных конструкций и pg_catalog/information_schema."""
import pytest

from app.mcp.server.policy import (
    PolicyError,
    SQL_MAX_ROWS,
    validate_k,
    validate_query,
    validate_sql,
)


def test_validate_sql_delete_raises():
    """DELETE FROM ... -> PolicyError."""
    with pytest.raises(PolicyError) as exc_info:
        validate_sql("DELETE FROM llm.kb_documents WHERE doc_id = 'x'")
    assert "Only SELECT" in str(exc_info.value) or "Forbidden" in str(exc_info.value)


def test_validate_sql_insert_raises():
    """INSERT INTO ... -> PolicyError."""
    with pytest.raises(PolicyError):
        validate_sql("INSERT INTO llm.kb_documents (doc_key) VALUES ('x')")


def test_validate_sql_semicolon_batch_raises():
    """SELECT ...; DROP TABLE ... -> PolicyError (semicolon or forbidden keyword)."""
    with pytest.raises(PolicyError):
        validate_sql("SELECT * FROM llm.kb_documents LIMIT 1; DROP TABLE llm.kb_documents")


def test_validate_sql_pg_catalog_raises():
    """SELECT * FROM pg_catalog.pg_tables -> PolicyError."""
    with pytest.raises(PolicyError) as exc_info:
        validate_sql("SELECT * FROM pg_catalog.pg_tables")
    assert "pg_catalog" in str(exc_info.value).lower() or "not allowed" in str(exc_info.value).lower()


def test_validate_sql_information_schema_raises():
    """Доступ к information_schema запрещён."""
    with pytest.raises(PolicyError):
        validate_sql("SELECT * FROM information_schema.tables")


def test_validate_sql_valid_select_ok():
    """Валидный SELECT * FROM llm.kb_documents LIMIT 10 -> без исключения."""
    validate_sql("SELECT * FROM llm.kb_documents LIMIT 10")
    validate_sql("  SELECT doc_id, title FROM llm.kb_chunks WHERE chunk_index < 5")


def test_validate_k_valid_range():
    """k в диапазоне 1..10 принимается."""
    for k in (1, 5, 10):
        validate_k(k)


def test_validate_k_out_of_range_raises():
    """k > 10 -> PolicyError."""
    with pytest.raises(PolicyError) as exc_info:
        validate_k(11)
    assert "10" in str(exc_info.value)


def test_validate_query_empty_raises():
    """Пустой/None query -> PolicyError."""
    with pytest.raises(PolicyError):
        validate_query(None)  # type: ignore[arg-type]


def test_validate_query_too_long_raises():
    """query длиннее 1000 символов -> PolicyError."""
    with pytest.raises(PolicyError):
        validate_query("x" * 1001)


def test_sql_max_rows_constant():
    """Лимит строк для sql_read — 200 (enforcement в execute_readonly_sql)."""
    assert SQL_MAX_ROWS == 200
