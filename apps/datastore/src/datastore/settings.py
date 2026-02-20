"""Настройки datastore: путь к данным и подпапки."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Имена подпапок под DATA_PATH
KNOWLEDGE_BASE_DIR = "knowledge_base"
DEMO_DIR = "demo"


class Settings(BaseSettings):
    """Настройки приложения (env DATA_PATH)."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="",
    )

    data_path: str = "/app/data"  # env: DATA_PATH

    @property
    def knowledge_base_path(self) -> Path:
        return Path(self.data_path) / KNOWLEDGE_BASE_DIR

    @property
    def demo_path(self) -> Path:
        return Path(self.data_path) / DEMO_DIR
