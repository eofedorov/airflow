"""Agent loop: LLM + MCP tool-calls -> финальный AnswerContract; лимит вызовов; insufficient_context."""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.contracts.rag_schemas import AnswerContract
from app.services.rag_agent import MAX_TOOL_CALLS_PER_REQUEST, ask


def _make_tool_call(tc_id: str, name: str, arguments: dict):
    """Минимальный объект tool_call для choice.message.tool_calls."""
    fn = MagicMock()
    fn.name = name
    fn.arguments = json.dumps(arguments)
    tc = MagicMock()
    tc.id = tc_id
    tc.function = fn
    return tc


def _make_message(content: str | None = None, tool_calls: list | None = None):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    return msg


def _make_completion(message):
    comp = MagicMock()
    comp.choices = [MagicMock()]
    comp.choices[0].message = message
    return comp


def test_agent_kb_search_then_kb_get_chunk_returns_ok():
    """LLM вызывает kb_search -> kb_get_chunk -> финальный ответ с status ok."""
    tools_def = [
        {"type": "function", "function": {"name": "kb_search", "description": "Search KB"}},
        {"type": "function", "function": {"name": "kb_get_chunk", "description": "Get chunk"}},
    ]
    call_count = [0]

    def mock_list_tools(mcp_url=None):
        return tools_def

    def mock_call_tool(name, args, mcp_url=None, run_id=None):
        if name == "kb_search":
            return {
                "chunks": [
                    {"id": "chunk-1", "score": 0.9, "doc_meta": {"title": "Runbook"}, "preview": "Redis eviction..."},
                ],
            }
        if name == "kb_get_chunk":
            return {"chunk_id": "chunk-1", "text": "Use CART_CACHE_BYPASS=true.", "meta": {}, "found": True}
        return {}

    def mock_llm(messages, tools):
        call_count[0] += 1
        if call_count[0] == 1:
            return _make_completion(_make_message(
                content=None,
                tool_calls=[_make_tool_call("tc1", "kb_search", {"query": "Redis cache", "k": 5})],
            ))
        if call_count[0] == 2:
            return _make_completion(_make_message(
                content=None,
                tool_calls=[_make_tool_call("tc2", "kb_get_chunk", {"chunk_id": "chunk-1"})],
            ))
        return _make_completion(_make_message(content=json.dumps({
            "answer": "Enable CART_CACHE_BYPASS=true.",
            "confidence": 0.85,
            "sources": [{"chunk_id": "chunk-1", "doc_title": "Runbook", "quote": "CART_CACHE_BYPASS=true", "relevance": 0.9}],
            "status": "ok",
        })))

    with (
        patch("app.services.rag_agent.mcp_list_tools", side_effect=mock_list_tools),
        patch("app.services.rag_agent.mcp_call_tool", side_effect=mock_call_tool),
        patch("app.services.rag_agent.llm_client.call_llm_with_tools", side_effect=mock_llm),
    ):
        result = ask("How to fix Redis cart?")

    assert isinstance(result, AnswerContract)
    assert result.status == "ok"
    assert len(result.sources) == 1
    assert "CART_CACHE_BYPASS" in result.answer or "cache" in result.answer.lower()


def test_agent_max_tool_calls_limit():
    """После max_tool_calls итераций цикл прекращается, возвращается insufficient_context."""
    tools_def = [{"type": "function", "function": {"name": "kb_search", "description": "Search"}}]
    llm_call_count = [0]

    def mock_llm(messages, tools):
        llm_call_count[0] += 1
        # Каждый раз LLM просит ещё один tool_call
        return _make_completion(_make_message(
            content=None,
            tool_calls=[_make_tool_call(f"tc{llm_call_count[0]}", "kb_search", {"query": "x", "k": 5})],
        ))

    def mock_call_tool(name, args, mcp_url=None, run_id=None):
        return {"chunks": []}

    with (
        patch("app.services.rag_agent.mcp_list_tools", return_value=tools_def),
        patch("app.services.rag_agent.mcp_call_tool", side_effect=mock_call_tool),
        patch("app.services.rag_agent.llm_client.call_llm_with_tools", side_effect=mock_llm),
    ):
        result = ask("Question?")

    assert result.status == "insufficient_context"
    assert llm_call_count[0] <= MAX_TOOL_CALLS_PER_REQUEST + 1


def test_agent_insufficient_context_when_no_tools():
    """При пустом list_tools возвращается insufficient_context без вызова LLM."""
    with patch("app.services.rag_agent.mcp_list_tools", return_value=[]):
        result = ask("Any question?")

    assert result.status == "insufficient_context"
    assert result.sources == []


def test_agent_insufficient_context_when_empty_search_results():
    """LLM получает пустые chunks от kb_search -> в итоге может вернуть insufficient (или ok с пустыми sources)."""
    tools_def = [{"type": "function", "function": {"name": "kb_search", "description": "Search"}}]

    def mock_llm(messages, tools):
        # Первый вызов: tool_call kb_search
        if len(messages) <= 3:
            return _make_completion(_make_message(
                content=None,
                tool_calls=[_make_tool_call("tc1", "kb_search", {"query": "nonexistent", "k": 5})],
            ))
        # После результата пустого поиска — финальный ответ insufficient
        return _make_completion(_make_message(content=json.dumps({
            "answer": "In the knowledge base there is no answer to this question.",
            "confidence": 0.0,
            "sources": [],
            "status": "insufficient_context",
        })))

    def mock_call_tool(name, args, mcp_url=None, run_id=None):
        return {"chunks": []}

    with (
        patch("app.services.rag_agent.mcp_list_tools", return_value=tools_def),
        patch("app.services.rag_agent.mcp_call_tool", side_effect=mock_call_tool),
        patch("app.services.rag_agent.llm_client.call_llm_with_tools", side_effect=mock_llm),
    ):
        result = ask("Something that is not in KB?")

    assert result.status == "insufficient_context"
    assert len(result.sources) == 0
