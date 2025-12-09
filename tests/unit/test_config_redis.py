import os
from unittest.mock import patch
from meridian.config import DevConfig, RedisOnlineStore, InMemoryOnlineStore


def test_dev_config_auto_redis() -> None:
    config = DevConfig()

    # 1. No env var -> Memory
    with patch.dict(os.environ, {}, clear=True):
        store = config.get_online_store()
        assert isinstance(store, InMemoryOnlineStore)

    # 2. Redis env var -> Redis (if available)
    # We need to mock RedisOnlineStore presence if it's conditional import
    # But it is imported in test? config.py imports it safely.
    # If RedisOnlineStore is None (no redis installed), it falls back to Memory?
    # Logic: if redis_url and RedisOnlineStore: ...

    # Assuming we have redis installed in dev env.
    if RedisOnlineStore is not None:
        with patch.dict(os.environ, {"MERIDIAN_REDIS_URL": "redis://localhost:6379"}):
            store = config.get_online_store()
            assert isinstance(store, RedisOnlineStore)
            assert store.connection_kwargs["url"] == "redis://localhost:6379"
