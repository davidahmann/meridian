import pytest
import pandas as pd
from meridian.store.postgres import PostgresOfflineStore
from testcontainers.postgres import PostgresContainer


# Skip if Docker is not available or if we want to run fast tests only
@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_offline_store_basic() -> None:
    # Use testcontainers to spin up a real Postgres instance
    try:
        postgres = PostgresContainer("postgres:15")
        postgres.start()
        connection_url = postgres.get_connection_url()
    except Exception:
        pytest.skip("Docker not available or failed to start Postgres container")

    try:
        # 1. Setup Store
        store = PostgresOfflineStore(connection_string=connection_url)

        # 2. Create Entity DataFrame
        entity_df = pd.DataFrame(
            {
                "user_id": ["u1", "u2"],
                "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            }
        )

        # 3. Get Training Data
        training_df = await store.get_training_data(
            entity_df, features=["user_transaction_count"]
        )

        # 4. Assertions
        assert len(training_df) == 2
        assert "user_id" in training_df.columns

    finally:
        postgres.stop()
