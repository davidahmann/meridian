import pytest
import pandas as pd
from datetime import datetime
from fabra.store.postgres import PostgresOfflineStore
from sqlalchemy import text
from typing import Dict, Any


# Use shared infrastructure fixture
@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_offline_store_basic(infrastructure: Dict[str, Any]) -> None:
    postgres_url = infrastructure["postgres_url"]
    store = PostgresOfflineStore(connection_string=postgres_url)

    # 1. Setup Data for basic retrieval test
    async with store.engine.begin() as conn:
        # Drop table if exists to ensure clean state (session scope fixture persists data)
        await conn.execute(text("DROP TABLE IF EXISTS features"))
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

    features_df = await store.get_training_data(
        entity_df, ["features"], "entity_id", "timestamp"
    )

    assert len(features_df) == 2
    assert "features" in features_df.columns
    assert features_df.iloc[0]["features"] == 100
    assert features_df.iloc[1]["features"] == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_context_operations(infrastructure: Dict[str, Any]) -> None:
    """Test get_context and list_contexts."""
    postgres_url = infrastructure["postgres_url"]
    store = PostgresOfflineStore(connection_string=postgres_url)

    # Clean context log table
    async with store.engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS context_log"))

    # 1. Write Context Log
    ctx_id_1 = "ctx_1"
    await store.log_context(
        context_id=ctx_id_1,
        timestamp=datetime(2024, 1, 1, 10, 0, 0),
        content="Hello World",
        lineage={"source": "test"},
        meta={"name": "test_ctx", "freshness_status": "fresh"},
        version="v1",
    )

    ctx_id_2 = "ctx_2"
    await store.log_context(
        context_id=ctx_id_2,
        timestamp=datetime(2024, 1, 1, 11, 0, 0),
        content="Hello Universe",
        lineage={"source": "test2"},
        meta={"name": "test_ctx_2", "freshness_status": "degraded"},
        version="v1",
    )

    # 2. Get Context
    ctx1 = await store.get_context(ctx_id_1)
    assert ctx1 is not None
    assert ctx1["context_id"] == ctx_id_1
    assert ctx1["content"] == "Hello World"
    assert ctx1["meta"]["name"] == "test_ctx"

    # 3. List Contexts
    all_contexts = await store.list_contexts()
    assert len(all_contexts) == 2
    # Ordered by timestamp DESC usually? Code says ORDER BY timestamp DESC
    assert all_contexts[0]["context_id"] == ctx_id_2

    # 4. List with Filter (Name)
    named = await store.list_contexts(name="test_ctx")
    assert len(named) == 1
    assert named[0]["context_id"] == ctx_id_1

    # 5. List with Filter (Freshness)
    degraded = await store.list_contexts(freshness_status="degraded")
    assert len(degraded) == 1
    assert degraded[0]["context_id"] == ctx_id_2
