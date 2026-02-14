"""Опциональный учёт токенов/стоимости. При наличии usage в ответе API — возвращает счётчики."""
from typing import Any


def get_usage_from_response(response: Any) -> dict[str, int]:
    """
    Из ответа OpenAI (или аналога) извлечь usage.
    Возвращает {"prompt_tokens": N, "completion_tokens": M} или пустой dict.
    """
    if response is None:
        return {}
    if hasattr(response, "usage") and response.usage:
        u = response.usage
        return {
            "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
        }
    return {}
