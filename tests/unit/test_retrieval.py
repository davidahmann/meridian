import pytest
from unittest.mock import MagicMock, AsyncMock
from meridian.retrieval import Retriever, RetrieverRegistry, retriever
from datetime import timedelta
from typing import List, Dict, Any


def test_registry() -> None:
    r = RetrieverRegistry()
    ret = Retriever(name="test", func=lambda: [])
    r.register(ret)
    assert r.get("test") == ret


def test_decorator_registration() -> None:
    @retriever(name="async_search")  # type: ignore[untyped-decorator]
    async def async_search(query: str) -> List[Dict[str, Any]]:
        return [{"text": query}]

    # Check attached metadata
    assert hasattr(async_search, "_meridian_retriever")
    ret_obj = getattr(async_search, "_meridian_retriever")
    assert ret_obj.backend == "custom"


@pytest.mark.asyncio
async def test_caching_logic() -> None:
    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    # Mock Store with online store
    store = MagicMock()
    store.online_store.redis = mock_redis

    # Define async retriever with caching
    @retriever(name="async_search", cache_ttl=timedelta(minutes=5))  # type: ignore[untyped-decorator]
    async def async_search(q: str) -> List[Dict[str, Any]]:
        return [{"result": q}]

    # Manually register to inject backend (simulating store.register_retriever)
    ret_obj = getattr(async_search, "_meridian_retriever")
    setattr(ret_obj, "_cache_backend", mock_redis)

    # 1. Call (Cache Miss)
    res = await async_search("test")
    assert res == [{"result": "test"}]
    mock_redis.get.assert_called_once()
    mock_redis.set.assert_called_once()

    # 2. Call (Cache Hit)
    import json

    mock_redis.get.return_value = json.dumps([{"result": "cached"}])
    mock_redis.reset_mock()

    res2 = await async_search("test")
    assert res2 == [{"result": "cached"}]
    mock_redis.get.assert_called_once()
    mock_redis.set.assert_not_called()
