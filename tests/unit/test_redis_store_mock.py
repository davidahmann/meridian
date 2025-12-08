import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from meridian.store.redis import RedisOnlineStore
import pandas as pd
from typing import Any


@pytest.fixture
def mock_redis() -> Any:
    with patch("meridian.store.redis.redis.Redis") as MockRedis:
        # Create the instance that will be returned
        instance = MagicMock()

        # Configure AsyncMocks for async methods
        instance.hmget = AsyncMock()
        instance.hset = AsyncMock()
        instance.expire = AsyncMock()
        instance.get = AsyncMock()
        instance.set = AsyncMock()
        instance.delete = AsyncMock()

        # Configure pipeline
        pipeline = MagicMock()  # The pipeline object itself
        pipeline.__aenter__ = AsyncMock(return_value=pipeline)
        pipeline.__aexit__ = AsyncMock()
        pipeline.hset = MagicMock()  # Pipeline methods are usually sync building
        pipeline.expire = MagicMock()
        pipeline.execute = AsyncMock()

        instance.pipeline.return_value = pipeline

        # Configure factory methods to return this instance
        MockRedis.from_url.return_value = instance
        # If constructor used
        MockRedis.return_value = instance

        yield instance


@pytest.mark.asyncio
async def test_redis_init(mock_redis: Any) -> None:
    store = RedisOnlineStore("redis://localhost")
    assert store.client == mock_redis


@pytest.mark.asyncio
async def test_redis_get_online_features(mock_redis: Any) -> None:
    # Setup return value
    mock_redis.hmget.return_value = [json.dumps(10), json.dumps(20.5)]

    store = RedisOnlineStore("redis://mock")

    res = await store.get_online_features("User", "u1", ["f1", "f2"])

    mock_redis.hmget.assert_called_once()
    assert res["f1"] == 10
    assert res["f2"] == 20.5


@pytest.mark.asyncio
async def test_redis_set_online_features(mock_redis: Any) -> None:
    store = RedisOnlineStore("redis://mock")

    await store.set_online_features("User", "u1", {"f1": 10}, ttl=60)

    mock_redis.hset.assert_called()
    mock_redis.expire.assert_called()


@pytest.mark.asyncio
async def test_redis_bulk(mock_redis: Any) -> None:
    store = RedisOnlineStore("redis://mock")
    df = pd.DataFrame({"id": ["u1"], "f1": [100]})

    await store.set_online_features_bulk("User", df, "f1", "id")

    # Check pipeline execution
    pipeline = mock_redis.pipeline.return_value
    pipeline.execute.assert_called()


@pytest.mark.asyncio
async def test_redis_primitives(mock_redis: Any) -> None:
    store = RedisOnlineStore("redis://mock")

    await store.get("k")
    mock_redis.get.assert_called()

    await store.set("k", "v")
    mock_redis.set.assert_called()
