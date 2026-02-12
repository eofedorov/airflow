"""Конфигурация приложения из переменных окружения."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_base_url: str = ""  # например https://models.github.ai/inference/v1 для GitHub Models
    llm_model: str = "gpt-4o-mini"
    llm_max_tokens: int = 1024
    llm_timeout: int = 60
    llm_max_retries: int = 2
    enable_token_meter: bool = False
