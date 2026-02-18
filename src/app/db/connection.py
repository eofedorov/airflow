"""Пул соединений Postgres (singleton)."""
from psycopg_pool import ConnectionPool

from app.settings import Settings

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Singleton пул соединений. Использует DATABASE_URL из настроек."""
    global _pool
    if _pool is None:
        url = Settings().database_url
        _pool = ConnectionPool(
            conninfo=url,
            min_size=1,
            max_size=10,
        )
    return _pool


def close_pool() -> None:
    """Закрыть пул (для тестов или shutdown)."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
