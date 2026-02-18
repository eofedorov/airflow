"""
Agent loop: вопрос пользователя -> LLM с tools (MCP) -> до 6 вызовов инструментов -> финальный ответ AnswerContract.
"""
import json
import logging
from uuid import UUID

from app.contracts.rag_schemas import AnswerContract
from app.llm import client as llm_client
from app.mcp.client.mcp_client import call_tool as mcp_call_tool
from app.mcp.client.mcp_client import list_tools as mcp_list_tools
from app.mcp.server.policy import MAX_TOOL_CALLS_PER_REQUEST

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты отвечаешь на вопросы по базе знаний. Обязательно используй инструменты kb_search и kb_get_chunk для поиска и получения текста чанков.
Если по результатам поиска данных недостаточно для ответа — верни status "insufficient_context".
Финальный ответ выводи строго в виде одного JSON-объекта со схемой: {"answer": "...", "confidence": 0.0-1.0, "sources": [{"chunk_id": "...", "doc_title": "...", "quote": "...", "relevance": 0.0-1.0}], "status": "ok" | "insufficient_context"}.
Не добавляй текст до или после JSON."""

INSUFFICIENT_ANSWER = "In the knowledge base there is no answer to this question."


def _extract_json_from_text(text: str) -> str:
    """Вырезать JSON из текста (между первой { и последней })."""
    text = text.strip()
    start = text.find("{")
    if start == -1:
        return text
    end = text.rfind("}")
    if end == -1 or end < start:
        return text
    return text[start : end + 1]


def _parse_answer(content: str | None) -> AnswerContract | None:
    """Распарсить content в AnswerContract. При ошибке — None."""
    if not content or not content.strip():
        return None
    raw = _extract_json_from_text(content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    try:
        return AnswerContract.model_validate(data)
    except Exception:
        return None


def ask(
    question: str,
    run_id: UUID | str | None = None,
    mcp_url: str | None = None,
) -> AnswerContract:
    """
    Agent loop: получить tools из MCP -> цикл LLM + tool_calls (до 6 вызовов) -> разобрать финальный ответ в AnswerContract.
    При отсутствии валидного ответа или превышении лимита возвращает insufficient_context.
    """
    tools = mcp_list_tools(mcp_url)
    if not tools:
        logger.warning("[rag_agent] no MCP tools, returning insufficient_context")
        return AnswerContract(
            answer=INSUFFICIENT_ANSWER,
            confidence=0.0,
            sources=[],
            status="insufficient_context",
        )

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question.strip()},
    ]
    total_tool_calls = 0

    while total_tool_calls < MAX_TOOL_CALLS_PER_REQUEST:
        completion = llm_client.call_llm_with_tools(messages, tools)
        choice = completion.choices[0] if completion.choices else None
        if not choice:
            break
        msg = choice.message
        content = getattr(msg, "content", None) if msg else None
        tool_calls = getattr(msg, "tool_calls", None) if msg else []

        if not tool_calls and content:
            parsed = _parse_answer(content)
            if parsed is not None:
                return parsed
            return AnswerContract(
                answer=INSUFFICIENT_ANSWER,
                confidence=0.0,
                sources=[],
                status="insufficient_context",
            )

        if not tool_calls:
            break

        assistant_msg: dict = {"role": "assistant", "content": content or ""}
        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"},
            }
            for tc in tool_calls
        ]
        messages.append(assistant_msg)

        for tc in tool_calls:
            if total_tool_calls >= MAX_TOOL_CALLS_PER_REQUEST:
                break
            name = tc.function.name
            try:
                args_str = tc.function.arguments or "{}"
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}
            try:
                result = mcp_call_tool(name, args, mcp_url=mcp_url, run_id=run_id)
                result_str = json.dumps(result, ensure_ascii=False)
            except Exception as e:
                logger.exception("[rag_agent] mcp call_tool failed: %s", e)
                result_str = json.dumps({"error": str(e)}, ensure_ascii=False)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })
            total_tool_calls += 1

    return AnswerContract(
        answer=INSUFFICIENT_ANSWER,
        confidence=0.0,
        sources=[],
        status="insufficient_context",
    )
