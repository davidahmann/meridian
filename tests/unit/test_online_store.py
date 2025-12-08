import pytest
import pandas as pd
from meridian.store.online import InMemoryOnlineStore


@pytest.mark.asyncio
async def test_in_memory_online_store_basic() -> None:
    store = InMemoryOnlineStore()

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
        feature_names=["transaction_count", "avg_spend", "missing_feature"],
    )

    # 3. Assertions
    assert result["transaction_count"] == 5
    assert result["avg_spend"] == 100.0
    assert "missing_feature" not in result


@pytest.mark.asyncio
async def test_in_memory_online_store_bulk() -> None:
    store = InMemoryOnlineStore()
    df = pd.DataFrame({"user_id": ["u1", "u2"], "f1": [10, 20]})

    await store.set_online_features_bulk(
        entity_name="User", features_df=df, feature_name="f1", entity_id_col="user_id"
    )

    res1 = await store.get_online_features("User", "u1", ["f1"])
    assert res1["f1"] == 10

    res2 = await store.get_online_features("User", "u2", ["f1"])
    assert res2["f1"] == 20


@pytest.mark.asyncio
async def test_cache_primitives() -> None:
    store = InMemoryOnlineStore()

    # Set/Get
    await store.set("key1", b"val1")
    val = await store.get("key1")
    assert val == b"val1"

    # Delete
    count = await store.delete("key1")
    assert count == 1
    val_del = await store.get("key1")
    assert val_del is None

    # Smembers (Set ops)
    # Using pipeline for sadd usually, but implemented via dummy pipeline logic in memory store?
    # No, store.smembers(key) reads _set_storage.
    # But ONLY MockPipeline.sadd writes to _set_storage.
    # InMemoryOnlineStore doesn't expose sadd directly on 'self'?
    # Checking source: line 147 is pipeline.sadd. line 73: set_storage = {}.
    # Direct sadd not on InMemoryOnlineStore? It wasn't in abstract base class.
    # Ah, InMemoryOnlineStore doesn't seem to implement sadd directly in the code I viewed?
    # Let's check line 135 in previous view_file_outline (step 2028).
    # `smembers` is there. `sadd` is NOT on `OnlineStore` or `InMemoryOnlineStore` top level!
    # It is only on `pipeline()`.

    p = store.pipeline()
    p.sadd("setkey", "m1")
    p.sadd("setkey", "m2")
    await p.execute()

    members = await store.smembers("setkey")
    assert "m1" in members
    assert "m2" in members


@pytest.mark.asyncio
async def test_pipeline_methods() -> None:
    store = InMemoryOnlineStore()
    p = store.pipeline()

    p.set("pk1", b"v1")
    p.expire("pk1", 10)  # Should do nothing but not crash
    await p.execute()

    val = await store.get("pk1")
    assert val == b"v1"
