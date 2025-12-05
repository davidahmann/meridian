import pytest
import pandas as pd
from meridian.core import FeatureStore, entity, feature
from meridian.store.offline import DuckDBOfflineStore
from meridian.store.online import InMemoryOnlineStore


@pytest.mark.asyncio
async def test_hybrid_offline_retrieval() -> None:
    # 1. Setup Stores
    # Create a DuckDB store with some data
    offline_store = DuckDBOfflineStore()
    offline_store.conn.execute(
        "CREATE TABLE user_stats (entity_id VARCHAR, total_spend INTEGER)"
    )
    offline_store.conn.execute("INSERT INTO user_stats VALUES ('u1', 100), ('u2', 200)")

    store = FeatureStore(
        offline_store=offline_store, online_store=InMemoryOnlineStore()
    )

    @entity(store)
    class User:
        user_id: str

    # 2. Define Features
    # Python Feature
    @feature(entity=User)
    def name_len(user_id: str) -> int:
        return len(user_id)

    # SQL Feature
    # Note: We assume the table name matches the feature name for the MVP join logic
    # OR we need to adjust the test to match the MVP implementation.
    # In MVP DuckDBOfflineStore, we do: LEFT JOIN {feature} ON ...
    # So we need a table named 'total_spend' if the feature is named 'total_spend'.
    # Let's rename the table to match the feature.
    # Let's rename the table to match the feature.
    offline_store.conn.execute("ALTER TABLE user_stats RENAME TO total_spend")
    # Add timestamp column for PIT correctness
    offline_store.conn.execute(
        "ALTER TABLE total_spend ADD COLUMN timestamp TIMESTAMP DEFAULT '2024-01-01 00:00:00'"
    )

    @feature(entity=User, sql="SELECT * FROM total_spend")
    def total_spend(user_id: str) -> int:
        return 0  # Stub for Python, but SQL should take precedence in retrieval

    # 3. Create Entity DataFrame
    entity_df = pd.DataFrame(
        {
            "user_id": ["u1", "u2"],
            "timestamp": [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-02")],
        }
    )

    # 4. Get Training Data
    training_df = await store.get_training_data(entity_df, ["name_len", "total_spend"])

    # 5. Verify Results
    assert "name_len" in training_df.columns
    assert "total_spend" in training_df.columns

    # Check Python feature
    assert (
        training_df.loc[training_df["user_id"] == "u1", "name_len"].iloc[0] == 2
    )  # len("u1")

    # Check SQL feature
    assert training_df.loc[training_df["user_id"] == "u1", "total_spend"].iloc[0] == 100
    assert training_df.loc[training_df["user_id"] == "u2", "total_spend"].iloc[0] == 200


@pytest.mark.asyncio
async def test_materialization_flow() -> None:
    # 1. Setup Stores
    offline_store = DuckDBOfflineStore()
    offline_store.conn.execute(
        "CREATE TABLE high_value_users (entity_id VARCHAR, is_high_value BOOLEAN)"
    )
    offline_store.conn.execute(
        "INSERT INTO high_value_users VALUES ('u1', TRUE), ('u2', FALSE)"
    )

    online_store = InMemoryOnlineStore()
    store = FeatureStore(offline_store=offline_store, online_store=online_store)

    @entity(store)
    class User:
        user_id: str

    # 2. Define SQL Feature for Materialization
    # The SQL query in the definition is what gets executed.
    # It should return [entity_id, value] (aliased as feature name ideally, or just value)
    # The MVP materializer expects the query result to have columns.
    # And it uses `entity_def.id_column` to find the ID.
    # And `feature_name` to find the value.

    @feature(
        entity=User,
        sql="SELECT entity_id AS user_id, is_high_value FROM high_value_users",
        materialize=True,
    )
    def is_high_value(user_id: str) -> bool:
        return False

    # 3. Run Materialization
    # We call the internal method directly for testing
    await store._materialize_feature_async("is_high_value")

    # 4. Verify Online Store
    # Check u1
    features_u1 = await online_store.get_online_features(
        "User", "u1", ["is_high_value"]
    )
    assert features_u1["is_high_value"] is True

    # Check u2
    features_u2 = await online_store.get_online_features(
        "User", "u2", ["is_high_value"]
    )
    assert features_u2["is_high_value"] is False
