import pytest
from unittest.mock import MagicMock, AsyncMock
from meridian.core import FeatureStore, entity, feature
from meridian.store.online import InMemoryOnlineStore


@pytest.mark.asyncio
async def test_fallback_to_compute() -> None:
    store = FeatureStore(online_store=InMemoryOnlineStore())

    @entity(store)
    class User:
        user_id: str

    @feature(entity=User)
    def computed_feature(user_id: str) -> int:
        return 100

    # Don't set online features, so it should miss cache and hit compute
    result = await store.get_online_features("User", "u1", ["computed_feature"])
    assert result["computed_feature"] == 100


@pytest.mark.asyncio
async def test_fallback_to_default() -> None:
    store = FeatureStore(online_store=InMemoryOnlineStore())

    @entity(store)
    class User:
        user_id: str

    @feature(entity=User, default_value=999)
    def failing_feature(user_id: str) -> int:
        raise ValueError("Compute failed")

    # Cache miss + Compute fail -> Default
    result = await store.get_online_features("User", "u1", ["failing_feature"])
    assert result["failing_feature"] == 999


@pytest.mark.asyncio
async def test_circuit_breaker() -> None:
    # Mock online store to fail
    mock_store = MagicMock()
    mock_store.get_online_features = AsyncMock(side_effect=Exception("Redis Down"))

    store = FeatureStore(online_store=mock_store)

    # Reset breaker (it's new per instance, so it starts closed, but good to be explicit if needed)
    store.online_store_breaker.close()

    @entity(store)
    class User:
        user_id: str

    @feature(entity=User, default_value=0)
    def simple_feature(user_id: str) -> int:
        return 1

    # Trigger failures to open breaker
    # fail_max is 5
    for _ in range(5):
        try:
            await store.get_online_features("User", "u1", ["simple_feature"])
        except Exception:
            pass

    # Next call should raise CircuitBreakerError internally, caught by our try/except,
    # and return default (since cache is skipped/failed).
    # We want to verify the breaker is OPEN.
    assert store.online_store_breaker.current_state == "open"

    # Even with breaker open, we should get result from compute or default
    result = await store.get_online_features("User", "u1", ["simple_feature"])
    assert (
        result["simple_feature"] == 1
    )  # Should hit compute since cache failed/skipped
