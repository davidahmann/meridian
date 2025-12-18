"""Integration tests for Fabra Worker."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from fabra.worker import AxiomWorker
from fabra.core import FeatureStore, Feature
import json


@pytest.fixture
def mock_store() -> MagicMock:
    store = MagicMock(spec=FeatureStore)
    store.online_store = MagicMock()
    # Mock redis pubsub
    pubsub = AsyncMock()

    # Needs to handle hasattr checks
    store.online_store.redis = MagicMock()
    store.online_store.redis.pubsub.return_value = pubsub

    # Mock subscribe
    pubsub.subscribe.return_value = None
    pubsub.get_message = AsyncMock(side_effect=[None])  # Return nothing first

    store.registry = MagicMock()
    # Setup feature registry
    store.registry.features = {
        "triggered_feature": Feature(
            name="triggered_feature",
            entity_name="user",
            func=lambda entity_id, event=None: f"processed_{entity_id}",
            trigger="user_events",
        )
    }
    # Mock get_features_by_trigger
    store.registry.get_features_by_trigger = MagicMock(
        return_value=[store.registry.features["triggered_feature"]]
    )
    store.registry.get_triggers = MagicMock(return_value=["user_events"])

    return store


@pytest.mark.asyncio
async def test_worker_init(mock_store: MagicMock) -> None:
    """Test worker initialization."""
    worker = AxiomWorker(store=mock_store)
    assert worker.store == mock_store
    # worker.running doesn't exist, check streams instead
    await worker.setup()
    assert "fabra:events:user_events" in worker.streams


@pytest.mark.asyncio
async def test_worker_process_event(mock_store: MagicMock) -> None:
    """Test processing a single event."""
    worker = AxiomWorker(store=mock_store)
    worker.ack = AsyncMock()  # type: ignore

    # Valid event payload
    event_data = {
        "event_type": "user_events",
        "entity_id": "u1",
        "payload": {"foo": "bar"},
    }

    msg_fields = {"data": json.dumps(event_data)}

    # We call internal method directly to test logic without loop
    await worker.process_message("stream", "msg_1", msg_fields)

    # Check trigger lookup
    mock_store.registry.get_features_by_trigger.assert_called_with("user_events")

    # Check materialization (set_online_features)
    mock_store.online_store.set_online_features.assert_called_once()
    call_kwargs = mock_store.online_store.set_online_features.call_args.kwargs
    assert call_kwargs["entity_name"] == "user"
    assert call_kwargs["entity_id"] == "u1"
    assert call_kwargs["features"] == {"triggered_feature": "processed_u1"}

    # Check ack
    worker.ack.assert_called_once_with("stream", "msg_1")


@pytest.mark.asyncio
async def test_worker_start_stop(mock_store: MagicMock) -> None:
    """Test worker start and graceful stop."""
    worker = AxiomWorker(store=mock_store)
    worker.redis = (
        AsyncMock()
    )  # Mock redis directly to avoid connection errors in run loop
    worker.setup = AsyncMock()  # Skip setup logic in this test
    worker.streams = ["fabra:events:test"]  # Manually set streams since setup is mocked

    # We throw CancelledError immediately in xreadgroup to exit the loop
    worker.redis.xreadgroup.side_effect = [
        []
    ]  # Just return empty then let loop continue?
    # Actually wait, if we want to stop it, we need to cancel it.
    # But run() catches CancelledError.
    # Easiest way is to define side_effect that raises CancelledError after 1 call
    import asyncio

    worker.redis.xreadgroup.side_effect = asyncio.CancelledError()

    await worker.run()
    # Should exit gracefully

    # Should close redis
    worker.redis.aclose.assert_called_once()
