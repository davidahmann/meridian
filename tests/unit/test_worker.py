import pytest
from unittest.mock import AsyncMock
from fabra.worker import AxiomWorker


@pytest.mark.asyncio
async def test_worker_setup() -> None:
    mock_redis = AsyncMock()
    # Mock return value for xgroup_create to raise nothing
    mock_redis.xgroup_create.return_value = None

    # Initialize with dummy URL to bypass config check
    worker = AxiomWorker(redis_url="redis://localhost:6379")
    worker.redis = mock_redis

    await worker.setup()

    # Verify it tried to create a consumer group for the default stream
    # xgroup_create(stream, group, id, mkstream)
    mock_redis.xgroup_create.assert_called()
    call_args = mock_redis.xgroup_create.call_args
    assert call_args[0][0] == "fabra:events:all"
    assert call_args[0][1] == "axiom_workers"
