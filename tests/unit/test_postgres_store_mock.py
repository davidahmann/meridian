import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from meridian.store.postgres import PostgresOfflineStore
import pandas as pd
from datetime import datetime
from typing import Any

# Path to patch
PATCH_PATH = "meridian.store.postgres.create_async_engine"


@pytest.fixture
def mock_engine_setup() -> Any:
    with patch(PATCH_PATH) as MockEngine:
        mock_engine = MagicMock()
        MockEngine.return_value = mock_engine

        mock_conn = AsyncMock()
        # Mocking async context manager for connect/begin
        mock_conn.__aenter__.return_value = mock_conn
        mock_conn.__aexit__.return_value = None

        mock_engine.connect.return_value = mock_conn
        mock_engine.begin.return_value = mock_conn

        yield mock_conn


@pytest.mark.asyncio
async def test_pg_get_training_data(mock_engine_setup: Any) -> None:
    store = PostgresOfflineStore("postgresql+asyncpg://mock")

    df = pd.DataFrame({"id": ["1"], "ts": [datetime.now()]})

    # Mock execute result
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_result.keys.return_value = ["entity_id", "timestamp", "f1"]

    mock_engine_setup.execute.return_value = mock_result

    res = await store.get_training_data(df, ["f1"], "id", "ts")

    assert isinstance(res, pd.DataFrame)
    mock_engine_setup.execute.assert_called()


@pytest.mark.asyncio
async def test_pg_search_vectors(mock_engine_setup: Any) -> None:
    store = PostgresOfflineStore("postgresql+asyncpg://mock")

    mock_result = MagicMock()
    Row = MagicMock()
    Row.content = "txt"
    Row.metadata = {}
    Row.score = 0.9
    mock_result.fetchall.return_value = [Row]

    mock_engine_setup.execute.return_value = mock_result

    res = await store.search("idx", [0.1], top_k=1)

    assert len(res) == 1
    assert res[0]["content"] == "txt"


@pytest.mark.asyncio
async def test_pg_add_documents(mock_engine_setup: Any) -> None:
    store = PostgresOfflineStore("postgresql+asyncpg://mock")

    await store.add_documents("idx", "doc1", ["c"], [[0.1]])

    mock_engine_setup.execute.assert_called()


@pytest.mark.asyncio
async def test_pg_time_travel(mock_engine_setup: Any) -> None:
    store = PostgresOfflineStore("postgresql+asyncpg://mock")

    mock_result = MagicMock()
    mock_row = MagicMock()
    # Mock row mapping for dict conversion
    mock_row._mapping = {"f1": 123}
    mock_result.fetchone.return_value = mock_row

    mock_engine_setup.execute.return_value = mock_result

    res = await store.get_historical_features("Ent", "e1", ["f1"], datetime.now())

    assert res["f1"] == 123
