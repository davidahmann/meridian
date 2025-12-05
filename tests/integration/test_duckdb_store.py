import pytest
import pandas as pd
from meridian.core import FeatureStore
from meridian.store.offline import DuckDBOfflineStore


@pytest.mark.asyncio
async def test_duckdb_offline_store_basic() -> None:
    # 1. Setup Store
    store = FeatureStore(offline_store=DuckDBOfflineStore())

    # 2. Create Entity DataFrame
    entity_df = pd.DataFrame(
        {
            "user_id": ["u1", "u2"],
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        }
    )

    # 3. Get Training Data (Mock implementation for now just returns entity_df)
    training_df = await store.get_training_data(
        entity_df, features=["user_transaction_count"]
    )

    # 4. Assertions
    assert len(training_df) == 2
    assert "user_id" in training_df.columns
    # Once we implement real joins, we'd assert the feature column exists too.
