"""
Запуск задачи: собрать контекст -> вызвать LLM -> валидировать -> repair при необходимости.
Возвращает валидный Pydantic-объект или результат с ошибкой. Логирование в шаге 8.
"""
import json
import logging
import time
from typing import Any

from app.llm import client as llm_client
from app.prompts.registry import get_prompt_by_name_version
from app.prompts.render import RenderContext, get_schema_description, render
from app.settings import Settings

logger = logging.getLogger(__name__)
_settings = Settings()

REPAIR_SYSTEM = "Преобразуй ответ в валидный JSON по указанной схеме. Выведи только JSON, без пояснений до или после."


def _parse_and_validate(raw: str, schema_class: type):
    """Распарсить JSON и провалидировать схемой. При ошибке — (None, error_message)."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"JSON decode error: {e}"
    try:
        model = schema_class.model_validate(data)
        return model, None
    except Exception as e:
        return None, f"Validation error: {e}"


def _extract_json_from_text(text: str) -> str:
    """Попытаться вырезать JSON из текста (между первой { и последней })."""
    text = text.strip()
    start = text.find("{")
    if start == -1:
        return text
    end = text.rfind("}")
    if end == -1 or end < start:
        return text
    return text[start : end + 1]


def run(
    prompt_name: str,
    version: str,
    task: str,
    input_data: str | dict,
    constraints: dict[str, Any] | None = None,
    *,
    _call_llm: Any = None,
) -> dict[str, Any]:
    """
    Выполнить промпт: render -> LLM -> validate -> при невалидном repair (1 попытка) -> ответ или ошибка.
    _call_llm: для тестов, подмена вызова LLM (callable(messages) -> str).
    Возврат: {"ok": True, "data": <Pydantic model dict>} или {"ok": False, "error": str, "diagnostics": str}.
    """
    call_llm = _call_llm if _call_llm is not None else llm_client.call_llm

    spec = get_prompt_by_name_version(prompt_name, version)
    if not spec:
        return {"ok": False, "error": "unknown prompt", "diagnostics": f"{prompt_name} {version}"}

    schema_class = spec.output_schema
    output_contract = get_schema_description(schema_class)
    context = RenderContext(
        task=task,
        input_data=input_data,
        constraints=constraints or {},
        output_contract=output_contract,
    )
    system_message, user_message = render(spec, context)
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]

    start = time.perf_counter()
    raw_response = call_llm(messages)
    elapsed = time.perf_counter() - start

    parsed = _extract_json_from_text(raw_response)
    model, err = _parse_and_validate(parsed, schema_class)
    if model is not None:
        logger.info(
            "runner ok prompt=%s version=%s elapsed_sec=%.2f model=%s repair=false",
            prompt_name, version, elapsed, _settings.llm_model,
        )
        return {"ok": True, "data": model.model_dump()}

    # repair: один повторный вызов с коротким системным промптом
    repair_messages = [
        {"role": "system", "content": REPAIR_SYSTEM + "\n\nСхема:\n" + output_contract[:1500]},
        {"role": "user", "content": "Исправь в валидный JSON:\n" + raw_response[:4000]},
    ]
    raw_repair = call_llm(repair_messages)
    elapsed_total = time.perf_counter() - start
    parsed_repair = _extract_json_from_text(raw_repair)
    model_repair, err_repair = _parse_and_validate(parsed_repair, schema_class)
    if model_repair is not None:
        logger.info(
            "runner ok after repair prompt=%s version=%s elapsed_sec=%.2f model=%s repair=true",
            prompt_name, version, elapsed_total, _settings.llm_model,
        )
        return {"ok": True, "data": model_repair.model_dump()}

    diagnostics = f"first: {err}; repair: {err_repair}"
    logger.warning(
        "runner validation failed prompt=%s version=%s elapsed_sec=%.2f model=%s repair=true parse_error=%s",
        prompt_name, version, elapsed_total, _settings.llm_model, diagnostics,
    )
    return {"ok": False, "error": "validation failed", "diagnostics": diagnostics}
