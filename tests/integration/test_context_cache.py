import pytest
from meridian.context import context, ContextItem
from meridian.core import FeatureStore
from meridian.store.online import InMemoryOnlineStore


@pytest.mark.asyncio
async def test_context_caching_behavior() -> None:
    store = FeatureStore()
    store.online_store = InMemoryOnlineStore()  # Simulated Redis

    # Track execution count
    execution_count = 0

    @context(name="cached_ctx", max_tokens=100)
    async def cached_ctx(user_id: str) -> list[ContextItem]:
        nonlocal execution_count
        execution_count += 1
        return [ContextItem(content="hello", priority=0)]

    # Manually wire cache backend for test
    cached_ctx._cache_backend = store.online_store  # type: ignore[attr-defined]

    # 1. First Call - Should Execute
    res1 = await cached_ctx("u1")
    assert execution_count == 1
    # Check content contains hello
    assert "hello" in res1.content

    # 2. Second Call - Should Hit Cache (assuming default cache enabled by decorator if cache_ttl set?)
    # Wait, checking decorator default. If cache_ttl not set, it might not cache.
    # Let's inspect decorator or explicit set TTL.
    # Re-defining with explicit TTL.

    execution_count = 0
    from datetime import timedelta

    @context(
        name="cached_ctx_explicit", max_tokens=100, cache_ttl=timedelta(seconds=60)
    )
    async def cached_ctx_explicit(user_id: str) -> list[ContextItem]:
        nonlocal execution_count
        execution_count += 1
        return [ContextItem(content="hello", priority=0)]

    # Manually wire cache backend for test
    cached_ctx_explicit._cache_backend = store.online_store  # type: ignore[attr-defined]

    # Call 1
    await cached_ctx_explicit("u2")
    assert execution_count == 1

    # Call 2
    await cached_ctx_explicit("u2")
    assert execution_count == 1  # Should NOT increment

    # Call 3 (Unique arg)
    await cached_ctx_explicit("u3")
    assert execution_count == 2
