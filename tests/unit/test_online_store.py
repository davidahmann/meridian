from meridian.store.online import InMemoryOnlineStore


def test_in_memory_online_store_basic() -> None:
    store = InMemoryOnlineStore()

    # 1. Set features
    store.set_online_features(
        entity_name="User",
        entity_id="u1",
        features={"transaction_count": 5, "avg_spend": 100.0},
    )

    # 2. Get features
    result = store.get_online_features(
        entity_name="User",
        entity_id="u1",
        feature_names=["transaction_count", "avg_spend", "missing_feature"],
    )

    # 3. Assertions
    assert result["transaction_count"] == 5
    assert result["avg_spend"] == 100.0
    assert "missing_feature" not in result


def test_in_memory_online_store_isolation() -> None:
    store = InMemoryOnlineStore()

    store.set_online_features("User", "u1", {"f1": 1})
    store.set_online_features("User", "u2", {"f1": 2})

    res1 = store.get_online_features("User", "u1", ["f1"])
    res2 = store.get_online_features("User", "u2", ["f1"])

    assert res1["f1"] == 1
    assert res2["f1"] == 2
