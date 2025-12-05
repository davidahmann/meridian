import pytest
import pandas as pd
from meridian.store.postgres import PostgresOfflineStore
from sqlalchemy import text
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
        # Note: We need to use postgresql+asyncpg for the async engine
        print(f"Original URL: {connection_url}")
        if "postgresql+psycopg2://" in connection_url:
            async_connection_url = connection_url.replace(
                "postgresql+psycopg2://", "postgresql+asyncpg://"
            )
        else:
            async_connection_url = connection_url.replace(
                "postgresql://", "postgresql+asyncpg://"
            )
        print(f"Async URL: {async_connection_url}")
        store = PostgresOfflineStore(connection_string=async_connection_url)

        # Create dummy data
        # We need to use sync engine for setup or run async setup
        # For simplicity in test, we can use the sync engine from testcontainers just for setup?
        # No, let's use the store's engine but we need to await it.

        async with store.engine.begin() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                text(
                    "CREATE TABLE features (entity_id VARCHAR, timestamp TIMESTAMP, features INTEGER)"
                )
            )
            await conn.execute(
                text("INSERT INTO features VALUES ('1', '2024-01-01 00:00:00', 100)")
            )
            await conn.execute(
                text("INSERT INTO features VALUES ('2', '2024-01-01 00:00:00', 200)")
            )

        # 2. Test Retrieval
        entity_df = pd.DataFrame(
            {
                "entity_id": ["1", "2"],
                "timestamp": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01")],
            }
        )

        # We need to pass entity_id_col and timestamp_col
        features_df = await store.get_training_data(
            entity_df, ["features"], "entity_id", "timestamp"
        )

        assert len(features_df) == 2
        assert "features" in features_df.columns
        # The column name from the query alias is 'features' (table name)
        assert features_df.iloc[0]["features"] == 100
        assert features_df.iloc[1]["features"] == 200

    finally:
        postgres.stop()
