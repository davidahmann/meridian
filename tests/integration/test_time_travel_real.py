import pytest
import pandas as pd
from datetime import datetime, timedelta, timezone
from meridian.store.postgres import PostgresOfflineStore
from sqlalchemy import text
import os

# Check if Docker is available/should run
docker_available = os.getenv("CI") is None  # heuristic


@pytest.mark.skipif(not docker_available, reason="Requires Docker/Local environment")
@pytest.mark.asyncio
async def test_time_travel_integration() -> None:
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")

    with PostgresContainer("postgres:15") as postgres:
        # testcontainers returns psycopg2 url, need asyncpg
        url = postgres.get_connection_url().replace("psycopg2", "asyncpg")
        store = PostgresOfflineStore(url)

        # Setup data
        async with store.engine.begin() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                text(
                    "CREATE TABLE price (entity_id TEXT, timestamp TIMESTAMPTZ, price INT)"
                )
            )

            now = datetime.now(timezone.utc)
            t1 = now - timedelta(hours=1)
            t2 = now  # current

            # Insert historical data
            await conn.execute(
                text("INSERT INTO price VALUES ('sku1', :t, 100)"), {"t": t1}
            )
            await conn.execute(
                text("INSERT INTO price VALUES ('sku1', :t, 200)"), {"t": t2}
            )

        # Case 1: Query at T1 + 30m (should see 100)
        query_ts = now - timedelta(minutes=30)
        entity_df = pd.DataFrame({"sku": ["sku1"], "ts": [query_ts]})

        res = await store.get_training_data(entity_df, ["price"], "sku", "ts")

        # Verify
        assert not res.empty
        assert "price" in res.columns
        # Should be 100
        assert res.iloc[0]["price"] == 100

        # Case 2: Query at T2 (should see 200)
        entity_df_2 = pd.DataFrame({"sku": ["sku1"], "ts": [now]})
        res_2 = await store.get_training_data(entity_df_2, ["price"], "sku", "ts")
        assert res_2.iloc[0]["price"] == 200
