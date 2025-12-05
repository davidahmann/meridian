import pytest
import pandas as pd
from meridian.core import FeatureStore, entity, feature
from meridian.store.offline import DuckDBOfflineStore
from meridian.store.online import InMemoryOnlineStore


@pytest.mark.asyncio
async def test_pit_correctness_duckdb() -> None:
    # 1. Setup Store
    offline_store = DuckDBOfflineStore()

    # Create feature table with history
    # User u1:
    # - T1 (2024-01-01 10:00): value = 10
    # - T3 (2024-01-01 12:00): value = 20
    offline_store.conn.execute(
        "CREATE TABLE txn_count (entity_id VARCHAR, timestamp TIMESTAMP, txn_count INTEGER)"
    )
    offline_store.conn.execute(
        "INSERT INTO txn_count VALUES ('u1', '2024-01-01 10:00:00', 10)"
    )
    offline_store.conn.execute(
        "INSERT INTO txn_count VALUES ('u1', '2024-01-01 12:00:00', 20)"
    )

    store = FeatureStore(
        offline_store=offline_store, online_store=InMemoryOnlineStore()
    )

    @entity(store)
    class User:
        user_id: str

    @feature(entity=User, sql="SELECT * FROM txn_count")
    def txn_count(user_id: str) -> int:
        return 0

    # 2. Query at T2 (2024-01-01 11:00) -> Should get 10 (latest value <= T2)
    entity_df_t2 = pd.DataFrame(
        {"user_id": ["u1"], "timestamp": pd.to_datetime(["2024-01-01 11:00:00"])}
    )

    training_df_t2 = await store.get_training_data(entity_df_t2, ["txn_count"])
    assert training_df_t2.iloc[0]["txn_count"] == 10

    # 3. Query at T4 (2024-01-01 13:00) -> Should get 20 (latest value <= T4)
    entity_df_t4 = pd.DataFrame(
        {"user_id": ["u1"], "timestamp": pd.to_datetime(["2024-01-01 13:00:00"])}
    )

    training_df_t4 = await store.get_training_data(entity_df_t4, ["txn_count"])
    assert training_df_t4.iloc[0]["txn_count"] == 20

    # 4. Query at T0 (2024-01-01 09:00) -> Should get NaN/None (no value <= T0)
    entity_df_t0 = pd.DataFrame(
        {"user_id": ["u1"], "timestamp": pd.to_datetime(["2024-01-01 09:00:00"])}
    )

    training_df_t0 = await store.get_training_data(entity_df_t0, ["txn_count"])
    # DuckDB returns NaN for missing joins usually, or None
    val = training_df_t0.iloc[0]["txn_count"]
    assert pd.isna(val) or val is None


@pytest.mark.asyncio
async def test_pit_correctness_postgres() -> None:
    from meridian.store.postgres import PostgresOfflineStore
    from testcontainers.postgres import PostgresContainer
    from sqlalchemy import text

    try:
        postgres = PostgresContainer("postgres:15")
        postgres.start()
        connection_url = postgres.get_connection_url()
    except Exception:
        pytest.skip("Docker not available or failed to start Postgres container")

    try:
        # 1. Setup Store
        if "postgresql+psycopg2://" in connection_url:
            async_connection_url = connection_url.replace(
                "postgresql+psycopg2://", "postgresql+asyncpg://"
            )
        else:
            async_connection_url = connection_url.replace(
                "postgresql://", "postgresql+asyncpg://"
            )
        offline_store = PostgresOfflineStore(connection_string=async_connection_url)

        # Create feature table with history
        async with offline_store.engine.begin() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                text(
                    "CREATE TABLE txn_count (entity_id VARCHAR, timestamp TIMESTAMP, txn_count INTEGER)"
                )
            )
            await conn.execute(
                text("INSERT INTO txn_count VALUES ('u1', '2024-01-01 10:00:00', 10)")
            )
            await conn.execute(
                text("INSERT INTO txn_count VALUES ('u1', '2024-01-01 12:00:00', 20)")
            )

        store = FeatureStore(
            offline_store=offline_store, online_store=InMemoryOnlineStore()
        )

        @entity(store)
        class User:
            user_id: str

        @feature(entity=User, sql="SELECT * FROM txn_count")
        def txn_count(user_id: str) -> int:
            return 0

        # 2. Query at T2 (2024-01-01 11:00) -> Should get 10
        entity_df_t2 = pd.DataFrame(
            {"user_id": ["u1"], "timestamp": pd.to_datetime(["2024-01-01 11:00:00"])}
        )

        training_df_t2 = await store.get_training_data(entity_df_t2, ["txn_count"])
        assert training_df_t2.iloc[0]["txn_count"] == 10

        # 3. Query at T4 (2024-01-01 13:00) -> Should get 20
        entity_df_t4 = pd.DataFrame(
            {"user_id": ["u1"], "timestamp": pd.to_datetime(["2024-01-01 13:00:00"])}
        )

        training_df_t4 = await store.get_training_data(entity_df_t4, ["txn_count"])
        assert training_df_t4.iloc[0]["txn_count"] == 20

    finally:
        postgres.stop()
