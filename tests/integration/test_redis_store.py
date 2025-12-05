import pytest
from meridian.store.redis import RedisOnlineStore
from testcontainers.redis import RedisContainer


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_online_store_basic() -> None:
    try:
        redis_container = RedisContainer("redis:7")
        redis_container.start()
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
    except Exception:
        pytest.skip("Docker not available or failed to start Redis container")

    try:
        store = RedisOnlineStore(host=host, port=port)

        # 1. Set features
        await store.set_online_features(
            entity_name="User",
            entity_id="u1",
            features={"transaction_count": 5, "avg_spend": 100.0},
        )

        # 2. Get features
        result = await store.get_online_features(
            entity_name="User",
            entity_id="u1",
            feature_names=["transaction_count", "avg_spend", "missing"],
        )

        # 3. Assertions
        assert result["transaction_count"] == 5
        assert result["avg_spend"] == 100.0
        assert "missing" not in result

    finally:
        redis_container.stop()
