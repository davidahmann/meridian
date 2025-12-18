import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from fabra.worker import AxiomWorker
from fabra.events import AxiomEvent

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.xgroup_create = AsyncMock()
    redis.xreadgroup = AsyncMock()
    redis.xadd = AsyncMock()
    redis.xack = AsyncMock()
    redis.aclose = AsyncMock()
    return redis


@pytest.fixture
def mock_store(mock_redis):
    """Create a mock FeatureStore."""
    store = MagicMock()
    # Ensure connections return our mock redis
    store.online_store = MagicMock()
    store.online_store.client = mock_redis
    store.online_store.set_online_features = AsyncMock()

    store.registry = MagicMock()
    store.registry.get_triggers = MagicMock(return_value=["user_login"])
    store.registry.get_features_by_trigger = MagicMock(return_value=[])

    return store


@pytest.fixture
async def worker(mock_store, mock_redis):
    """Create an AxiomWorker instance with mocked dependencies."""
    # We patch Redis.from_url to return our mock if needed,
    # but here we pass store which has the redis client.
    worker = AxiomWorker(store=mock_store)
    # Force the worker to use our mock redis regardless of init logic
    worker.redis = mock_redis
    return worker


# -----------------------------------------------------------------------------
# Lifecycle Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_setup_creates_groups(worker, mock_redis):
    """Test that setup creates consumer groups for streams."""
    # Setup worker with specific streams or let it infer from store
    # Store trigger is 'user_login' -> stream 'fabra:events:user_login'
    await worker.setup()

    # Check that xgroup_create was called
    mock_redis.xgroup_create.assert_awaited()
    # Should be called for 'fabra:events:user_login'
    call_args = mock_redis.xgroup_create.await_args
    assert call_args[0][0] == "fabra:events:user_login"
    assert call_args[0][1] == worker.group_name


@pytest.mark.asyncio
async def test_worker_setup_no_streams(mock_redis):
    """Test error when no streams are configured."""
    store = MagicMock()
    store.registry.get_triggers.return_value = []

    worker = AxiomWorker(store=store)
    worker.redis = mock_redis

    with pytest.raises(RuntimeError, match="No event streams"):
        await worker.setup()


@pytest.mark.asyncio
async def test_worker_setup_ignores_busygroup(worker, mock_redis):
    """Test that setup ignores BUSYGROUP errors."""
    # Simulate BUSYGROUP error
    mock_redis.xgroup_create.side_effect = Exception(
        "BUSYGROUP Consumer Group name already exists"
    )

    # Should not raise
    await worker.setup()
    mock_redis.xgroup_create.assert_awaited()


# -----------------------------------------------------------------------------
# Event Processing Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_message_success(worker, mock_store, mock_redis):
    """Test successful event processing and feature update."""
    # Logic:
    # 1. worker.process_message parses event
    # 2. Looks up features (mocked store)
    # 3. Executes feature function
    # 4. Updates online store
    # 5. Acks message

    # Mock event data
    event = AxiomEvent(
        event_type="user_login", entity_id="u123", payload={"ip": "1.2.3.4"}
    )
    event_json = event.model_dump_json()

    # Mock Feature
    mock_feature = MagicMock()
    mock_feature.name = "login_count"
    mock_feature.entity_name = "user"
    mock_feature.func = MagicMock(return_value=1)  # Function returns 1

    # Need to simulate signature for inspection
    # But inspection happens on feature.func. If it's a Mock, signature might be tricky.
    # We can just define a dummy function.
    def dummy_func(entity_id, event=None):
        return 1

    mock_feature.func = dummy_func

    # Setup Store Registry
    mock_store.registry.get_features_by_trigger.return_value = [mock_feature]

    # Call process_message
    msg_id = "1678888888888-0"
    fields = {"data": event_json}

    await worker.process_message("fabra:events:user_login", msg_id, fields)

    # Assertions
    # 1. Feature lookup called
    mock_store.registry.get_features_by_trigger.assert_called_with("user_login")

    # 2. Online store updated
    mock_store.online_store.set_online_features.assert_awaited_with(
        entity_name="user", entity_id="u123", features={"login_count": 1}
    )

    # 3. Message Acked
    mock_redis.xack.assert_awaited_with(
        "fabra:events:user_login", worker.group_name, msg_id
    )


@pytest.mark.asyncio
async def test_process_message_no_trigger(worker, mock_store, mock_redis):
    """Test event with no triggered features."""
    mock_store.registry.get_features_by_trigger.return_value = []

    event = AxiomEvent(event_type="unknown_event", entity_id="u1", payload={})
    event_json = event.model_dump_json()

    await worker.process_message("stream", "msg_id", {"data": event_json})

    # Lookup called
    mock_store.registry.get_features_by_trigger.assert_called_with("unknown_event")

    # NOT Updated
    mock_store.online_store.set_online_features.assert_not_awaited()

    # Acked (consumed but no-op)
    mock_redis.xack.assert_awaited()


@pytest.mark.asyncio
async def test_process_message_compute_error(worker, mock_store, mock_redis):
    """Test handler catches feature computation error without crashing."""
    # Feature raises exception
    mock_feature = MagicMock()
    mock_feature.name = "broken_feat"

    def broken_func(entity_id):
        raise ValueError("Computation Failed")

    mock_feature.func = broken_func

    mock_store.registry.get_features_by_trigger.return_value = [mock_feature]

    event = AxiomEvent(event_type="e", entity_id="u1", payload={})

    # Should NOT raise exception back to caller
    await worker.process_message("stream", "msg_id", {"data": event.model_dump_json()})

    # Acked even on error?
    # Logic in worker.py lines 164-165: catches logic error, then proceeds to next feature or finishes.
    # Line 169: await self.ack(stream, msg_id) is AFTER the feature loop.
    # So yes, it should ack if one feature fails (partial success).
    mock_redis.xack.assert_awaited()


# -----------------------------------------------------------------------------
# Error Handling (DLQ) Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_message_malformed_json(worker, mock_redis):
    """Test message with invalid JSON is moved to DLQ."""
    # Data is not valid JSON
    fields = {"data": "{invalid-json"}
    msg_id = "111-0"
    stream = "stream"

    await worker.process_message(stream, msg_id, fields)

    # Verify DLQ add
    # DLQ stream name: fabra:dlq:stream
    mock_redis.xadd.assert_awaited()
    call_args = mock_redis.xadd.await_args
    assert call_args[0][0] == "fabra:dlq:stream"
    assert "error" in call_args[0][1]

    # Original message acked
    mock_redis.xack.assert_awaited_with(stream, worker.group_name, msg_id)


@pytest.mark.asyncio
async def test_process_message_missing_data(worker, mock_redis):
    """Test message missing 'data' field."""
    # fields missing 'data'
    fields = {"other": "stuff"}
    msg_id = "222-0"

    await worker.process_message("stream", msg_id, fields)

    # Should just be acked and logged warning (no DLQ for missing data in current logic?)
    # Checking code...
    # Lines 121-124: if not data_str: logger.warning, await self.ack, return.
    # So NO DLQ in this case.

    mock_redis.xack.assert_awaited()
    mock_redis.xadd.assert_not_awaited()


# -----------------------------------------------------------------------------
# Integration Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_worker_loop_integration(worker, mock_redis, mock_store):
    """Test the full run loop processing messages."""
    # Mock xreadgroup to return one batch then raise CancelledError to stop loop
    event = AxiomEvent(event_type="test", entity_id="u1", payload={})
    fields = {"data": event.model_dump_json()}

    mock_redis.xreadgroup.side_effect = [
        # Batch 1
        [["fabra:events:test", [("1-0", fields)]]],
        # Batch 2 -> Stop
        asyncio.CancelledError(),
    ]

    # Mock setup to avoid real redis calls in run(), but set streams so logging works
    worker.setup = AsyncMock()
    worker.streams = ["fabra:events:test"]

    try:
        await worker.run()
    except asyncio.CancelledError:
        pass

    # Verify setup called
    worker.setup.assert_awaited()

    # Verify processing called
    mock_redis.xack.assert_awaited()

    # Verify xclose called
    mock_redis.aclose.assert_awaited()


@pytest.mark.asyncio
async def test_process_message_no_store(mock_redis):
    """Test processing when worker has no store (should log warning)."""
    # Worker with no store
    worker = AxiomWorker(store=None)
    worker.redis = mock_redis
    worker.group_name = "g"

    event = AxiomEvent(event_type="t", entity_id="u", payload={})
    fields = {"data": event.model_dump_json()}

    await worker.process_message("stream", "msg", fields)

    # Should warn and Ack
    mock_redis.xack.assert_awaited()


@pytest.mark.asyncio
async def test_worker_init_variations():
    """Test various initialization paths for Redis connection."""
    # 1. Store with .client
    store_mock = MagicMock()
    store_mock.online_store.client = "redis_client_1"
    w1 = AxiomWorker(store=store_mock)
    assert w1.redis == "redis_client_1"

    # 2. Store with .redis
    store_mock2 = MagicMock()
    del store_mock2.online_store.client
    store_mock2.online_store.redis = "redis_client_2"
    w2 = AxiomWorker(store=store_mock2)
    assert w2.redis == "redis_client_2"

    # 3. Redis URL in init
    with patch("fabra.worker.Redis.from_url") as mock_from_url:
        w3 = AxiomWorker(redis_url="redis://localhost")
        mock_from_url.assert_called_with("redis://localhost", decode_responses=True)
        assert w3.redis == mock_from_url.return_value

    # 4. Fallback to config (no store, no url provided)
    # Patch the SOURCE of the import because usage is a local import
    with patch("fabra.config.get_store_factory") as mock_get_factory, patch(
        "fabra.config.get_redis_url"
    ), patch("redis.asyncio.Redis.from_url") as mock_from_url:
        # Case 4a: get_store_factory returns something with client
        mock_online = MagicMock()
        mock_online.client = "redis_client_factory"
        # get_store_factory returns (offline, online)
        mock_get_factory.return_value = (None, mock_online)

        w4 = AxiomWorker()
        assert w4.redis == "redis_client_factory"
