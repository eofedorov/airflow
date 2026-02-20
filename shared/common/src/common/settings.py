"""Базовые настройки из env (database_url, qdrant_*, общие таймауты)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Корень репозитория: shared/common/src/common/settings.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_ENV_FILE = _REPO_ROOT / ".env"


class BaseAppSettings(BaseSettings):
    """Настройки, общие для нескольких сервисов (gateway, mcp_server, db)."""
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = ""
    qdrant_url: str = ""
    qdrant_collection: str = "kb_chunks_v1"
