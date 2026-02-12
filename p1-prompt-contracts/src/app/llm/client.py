from typing import Any
import os
from openai import OpenAI

from app.settings import Settings

_settings = Settings()


def _make_client() -> OpenAI:
    base_url = _settings.llm_base_url or None
    api_key = os.environ.get("GITHUB_TOKEN")
    if base_url:
        return OpenAI(base_url=base_url, api_key=api_key)
    return OpenAI(api_key=api_key)


def call_llm(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    timeout: int | None = None,
    max_retries: int | None = None,
) -> str:

    model = model or _settings.llm_model
    max_tokens = max_tokens if max_tokens is not None else _settings.llm_max_tokens
    timeout = timeout if timeout is not None else _settings.llm_timeout
    max_retries = max_retries if max_retries is not None else _settings.llm_max_retries

    client = _make_client()
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[_normalize_message(m) for m in messages],
                max_tokens=max_tokens,
                timeout=timeout,
            )
            if completion.choices:
                content = completion.choices[0].message.content
                if content:
                    return content.strip()
            return ""
        except Exception as e:
            last_error = e
            if attempt == max_retries:
                raise
            if "timeout" in str(e).lower() or "503" in str(e) or "502" in str(e) or "500" in str(e):
                continue
            raise
    raise last_error or RuntimeError("LLM call failed")


def _normalize_message(m: dict[str, Any]) -> dict[str, str]:
    """Ожидаемый формат: {"role": "system"|"user"|"assistant", "content": "..."}."""
    return {"role": str(m.get("role", "user")), "content": str(m.get("content", ""))}
