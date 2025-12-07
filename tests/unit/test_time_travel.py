import pytest
from unittest.mock import AsyncMock
from datetime import datetime
from typing import Dict, Any
from meridian.core import FeatureStore, get_context, get_current_timestamp
from meridian.store.offline import OfflineStore, DuckDBOfflineStore


@pytest.mark.asyncio
async def test_time_travel_context_var() -> None:
    # 1. Verify default is None
    assert get_current_timestamp() is None

    # 2. Verify get_context sets it
    ts = datetime(2023, 1, 1)

    async def mock_func() -> str:
        assert get_current_timestamp() == ts
        return "success"

    res = await get_context(mock_func, timestamp=ts)
    assert res == "success"

    # 3. Verify reset
    assert get_current_timestamp() is None


@pytest.mark.asyncio
async def test_feature_store_time_travel_routing() -> None:
    # Setup
    mock_offline = AsyncMock(spec=OfflineStore)
    mock_online = AsyncMock()

    fs = FeatureStore(offline_store=mock_offline, online_store=mock_online)
    fs.register_entity(name="user", id_column="user_id")
    fs.register_feature(name="f1", entity_name="user", func=lambda x: x)

    mock_offline.get_historical_features.return_value = {"f1": 100}
    mock_online.get_online_features.return_value = {"f1": 200}

    # 1. Real-time call (No timestamp)
    res_rt = await fs.get_online_features("user", "u1", ["f1"])
    # Should call online
    assert res_rt["f1"] == 200
    mock_online.get_online_features.assert_called_once()
    mock_offline.get_historical_features.assert_not_called()

    # Reset mocks
    mock_online.reset_mock()
    mock_offline.reset_mock()

    # 2. Time Travel call
    ts = datetime(2022, 1, 1)

    async def context_logic() -> Dict[str, Any]:
        # Inside context, calling get_online_features
        return await fs.get_online_features("user", "u1", ["f1"])

    res_tt = await get_context(context_logic, timestamp=ts)

    # Should call offline
    assert res_tt["f1"] == 100
    mock_offline.get_historical_features.assert_called_once()
    # Check args
    call_args = mock_offline.get_historical_features.call_args
    assert call_args.kwargs["timestamp"] == ts
    mock_online.get_online_features.assert_not_called()


@pytest.mark.asyncio
async def test_duckdb_historical_query() -> None:
    # Basic smoke test for query construction (using in-memory DuckDB)
    # We need to setup tables first
    store = DuckDBOfflineStore()

    # Create feature table 'f1'
    store.conn.execute(
        "CREATE TABLE f1 (entity_id VARCHAR, timestamp TIMESTAMP, f1 INTEGER)"
    )
    # Insert history
    # u1 at T1=10: value 10
    # u1 at T2=20: value 20
    store.conn.execute("INSERT INTO f1 VALUES ('u1', '2023-01-01 10:00:00', 10)")
    store.conn.execute("INSERT INTO f1 VALUES ('u1', '2023-01-01 12:00:00', 20)")

    # Query at 11:00:00 -> Should get 10
    ts_query = datetime(2023, 1, 1, 11, 0, 0)

    res = await store.get_historical_features("user", "u1", ["f1"], ts_query)
    assert res["f1"] == 10

    # Query at 13:00:00 -> Should get 20
    ts_query_2 = datetime(2023, 1, 1, 13, 0, 0)
    res2 = await store.get_historical_features("user", "u1", ["f1"], ts_query_2)
    assert res2["f1"] == 20
