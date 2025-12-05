import pytest
import pandas as pd
from sqlalchemy import text
from meridian.core import FeatureStore, entity, feature
from meridian.store.postgres import PostgresOfflineStore
from meridian.store.online import InMemoryOnlineStore
from testcontainers.postgres import PostgresContainer


@pytest.mark.asyncio
async def test_async_hybrid_flow() -> None:
    """
    Verify that we can retrieve both Python features (computed on-the-fly)
    and SQL features (retrieved from Async Postgres) in a single call.
    """
    with PostgresContainer("postgres:15") as postgres:
        # 1. Setup Postgres Store
        # Ensure we use the async driver
        connection_url = postgres.get_connection_url().replace("psycopg2", "asyncpg")
        offline_store = PostgresOfflineStore(connection_string=connection_url)

        # Create table for SQL feature
        async with offline_store.engine.begin() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                text(
                    "CREATE TABLE total_spend (entity_id VARCHAR, timestamp TIMESTAMP, total_spend INTEGER)"
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO total_spend VALUES ('u1', '2024-01-01 10:00:00', 100)"
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO total_spend VALUES ('u2', '2024-01-01 10:00:00', 200)"
                )
            )

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
        @feature(entity=User, sql="SELECT * FROM total_spend")
        def total_spend(user_id: str) -> int:
            return 0

        # 3. Create Entity DataFrame
        entity_df = pd.DataFrame(
            {
                "user_id": ["u1", "u2"],
                "timestamp": [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-02")],
            }
        )

        # 4. Get Training Data (Hybrid Retrieval)
        training_df = await store.get_training_data(
            entity_df, ["name_len", "total_spend"]
        )

        # 5. Verify Results
        assert "name_len" in training_df.columns
        assert "total_spend" in training_df.columns

        # Check Python feature
        assert (
            training_df.loc[training_df["user_id"] == "u1", "name_len"].iloc[0] == 2
        )  # len("u1")

        # Check SQL feature
        assert (
            training_df.loc[training_df["user_id"] == "u1", "total_spend"].iloc[0]
            == 100
        )
        assert (
            training_df.loc[training_df["user_id"] == "u2", "total_spend"].iloc[0]
            == 200
        )
