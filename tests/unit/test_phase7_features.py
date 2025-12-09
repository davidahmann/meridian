import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from meridian.worker import AxiomWorker
from meridian.server import create_app
from meridian.core import FeatureStore
from fastapi.testclient import TestClient


# --- DLQ Tests ---
@pytest.mark.asyncio
async def test_worker_dlq_logic() -> None:
    worker = AxiomWorker(redis_url="redis://mock")
    worker.redis = AsyncMock()

    # Mock message that causes error
    msg_id = "1-0"
    fields = {"data": "invalid-json"}

    # Patch ack method
    with patch.object(worker, "ack", new_callable=AsyncMock) as mock_ack:
        # process_message should catch error and route to DLQ
        await worker.process_message("stream1", msg_id, fields)

        # Verify XADD to DLQ
        assert worker.redis.xadd.called
        args = worker.redis.xadd.call_args
        assert args[0][0] == "meridian:dlq:stream1"
        assert args[0][1]["error"] is not None
        assert args[0][1]["data"] == "invalid-json"

        # Verify ACK
        mock_ack.assert_called_with("stream1", msg_id)


# --- Server Tests ---
@pytest.fixture
def mock_store() -> MagicMock:
    store = MagicMock(spec=FeatureStore)
    store.online_store = MagicMock()
    store.online_store.client = AsyncMock()  # Mock redis client
    # mocked get_online_features needs to return a dict, not a mock
    store.get_online_features = AsyncMock(return_value={"f": 1})
    return store


def test_audit_middleware(mock_store: MagicMock) -> None:
    app = create_app(mock_store)
    client = TestClient(app)

    with patch("meridian.server.logger") as mock_logger:
        # POST request should trigger audit
        client.post(
            "/v1/features",
            json={"entity_name": "E", "entity_id": "1", "features": ["f"]},
        )

        # Verify audit log
        audit_call = [
            c for c in mock_logger.info.call_args_list if "audit_log" in str(c)
        ]
        assert audit_call
        kwargs = audit_call[0].kwargs
        assert kwargs["audit"] is True
        assert kwargs["method"] == "POST"

        # GET request (health) should NOT trigger audit
        mock_logger.reset_mock()
        client.get("/health")
        audit_call_get = [
            c for c in mock_logger.info.call_args_list if "audit_log" in str(c)
        ]
        assert not audit_call_get


@pytest.mark.asyncio
async def test_cache_invalidation(mock_store: MagicMock) -> None:
    app = create_app(mock_store)
    client = TestClient(app)

    # Mock delete
    # Mock delete directly on the online_store, not client
    # because server logic checks hasattr(store.online_store, "delete")
    mock_store.online_store.delete = AsyncMock()

    res = client.delete("/v1/cache/User/u1")
    assert res.status_code == 200
    assert res.json()["status"] == "invalidated"

    mock_store.online_store.delete.assert_called_with("User:u1")
