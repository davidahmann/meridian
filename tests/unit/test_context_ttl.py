import pytest
from unittest.mock import AsyncMock, MagicMock
from meridian.context import context


@pytest.mark.asyncio
async def test_context_default_ttl() -> None:
    # We need to verify that cache_ttl is set on the wrapper or used.
    # Currently context wrapper doesn't expose its config easily except by behavior.
    # But we can inspect the closure or just rely on behavior if we inject a backend.

    mock_store = AsyncMock()
    # Mock pipeline for writes
    mock_pipeline = MagicMock()
    mock_pipeline.set.return_value = None
    mock_pipeline.sadd.return_value = None
    mock_pipeline.expire.return_value = None
    mock_pipeline.execute = AsyncMock(return_value=None)
    mock_store.pipeline = MagicMock(return_value=mock_pipeline)
    mock_store.set.return_value = None  # Trace write
    mock_store.get.return_value = None  # Miss

    @context(name="default_ttl_ctx")
    async def default_ttl_func() -> str:
        return "content"

    setattr(default_ttl_func, "_cache_backend", mock_store)

    await default_ttl_func()

    # Verify pipeline.set was called with ex=300 (5 mins)
    # pipeline.set(key, val, ex=300)
    # args[1] is kwargs, or just args. redis-py usually: set(name, value, ex=None, ...)
    # context.py: pipeline.set(cache_key, serialized, ex=int(cache_ttl.total_seconds()))

    assert mock_pipeline.set.called
    kwargs = mock_pipeline.set.call_args.kwargs
    if "ex" in kwargs:
        assert kwargs["ex"] == 300
    else:
        # call_args[0] = (key, val) ??
        # Only if pos args used.
        # context.py uses keyword 'ex'? No, positional usually?
        # "pipeline.set(cache_key, serialized, ex=...)" -> strict keyword usage for ex unless pos arg 3
        # Let's inspect call_args
        _, call_kwargs = mock_pipeline.set.call_args
        assert call_kwargs["ex"] == 300
