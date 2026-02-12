"""Конфигурация приложения из переменных окружения."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Корень проекта (p1-prompt-contracts): src/app/settings.py -> .. -> .. -> ..
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_base_url: str = ""
    llm_model: str = ""
    llm_max_tokens: int = 0
    llm_timeout: int = 0
    llm_max_retries: int = 0
    enable_token_meter: bool = False
