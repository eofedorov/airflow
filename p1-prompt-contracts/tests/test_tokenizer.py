"""Тесты подсчёта токенов (tiktoken)."""
import pytest

from app.llm.tokenizer import count_tokens
from app.settings import Settings

# Модель из конфига; в тестах при пустом значении — запасная для проверки подсчёта
_settings = Settings()
CONFIG_MODEL = _settings.llm_model


def test_count_tokens_empty():
    assert count_tokens([], CONFIG_MODEL) == 0
    assert count_tokens([{"role": "user", "content": "Hi"}], "") == 0


def test_count_tokens_single_message():
    messages = [{"role": "user", "content": "Hello"}]
    n = count_tokens(messages, CONFIG_MODEL)
    assert n > 0
    assert n < 50


def test_count_tokens_system_user():
    messages = [
        {"role": "system", "content": "You are a helper."},
        {"role": "user", "content": "Say OK."},
    ]
    n = count_tokens(messages, CONFIG_MODEL)
    assert n > 0
    assert n < 100


def test_count_tokens_unknown_model_fallback():
    """Неизвестная модель — fallback на o200k_base, без исключения."""
    messages = [{"role": "user", "content": "Test"}]
    n = count_tokens(messages, "unknown-model-xyz")
    assert n > 0
