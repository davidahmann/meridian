import os
from abc import ABC, abstractmethod

from meridian.store.offline import OfflineStore, DuckDBOfflineStore
from meridian.store.online import OnlineStore, InMemoryOnlineStore

# Try to import production stores (dependencies might not be installed in dev)
try:
    from meridian.store.postgres import PostgresOfflineStore
except ImportError:
    PostgresOfflineStore = None  # type: ignore

try:
    from meridian.store.redis import RedisOnlineStore
except ImportError:
    RedisOnlineStore = None  # type: ignore


class BaseConfig(ABC):
    @abstractmethod
    def get_offline_store(self) -> OfflineStore:
        pass

    @abstractmethod
    def get_online_store(self) -> OnlineStore:
        pass


class DevConfig(BaseConfig):
    def get_offline_store(self) -> OfflineStore:
        return DuckDBOfflineStore()

    def get_online_store(self) -> OnlineStore:
        return InMemoryOnlineStore()


class ProdConfig(BaseConfig):
    def get_offline_store(self) -> OfflineStore:
        if PostgresOfflineStore is None:
            raise ImportError(
                "PostgresOfflineStore not available. Install 'asyncpg' and 'sqlalchemy'."
            )

        url = os.environ.get("MERIDIAN_POSTGRES_URL")
        if not url:
            raise ValueError(
                "MERIDIAN_POSTGRES_URL environment variable is required for production."
            )
        return PostgresOfflineStore(connection_string=url)

    def get_online_store(self) -> OnlineStore:
        if RedisOnlineStore is None:
            raise ImportError("RedisOnlineStore not available. Install 'redis'.")

        url = os.environ.get("MERIDIAN_REDIS_URL")
        if not url:
            raise ValueError(
                "MERIDIAN_REDIS_URL environment variable is required for production."
            )
        return RedisOnlineStore(redis_url=url)


def get_config() -> BaseConfig:
    env = os.environ.get("MERIDIAN_ENV", "development").lower()
    if env == "production":
        return ProdConfig()
    return DevConfig()


def get_store_factory() -> tuple[OfflineStore, OnlineStore]:
    """Helper to get both stores at once."""
    config = get_config()
    return config.get_offline_store(), config.get_online_store()
