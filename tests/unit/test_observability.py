import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta
from meridian.context import context
from meridian.server import create_app
from fastapi.testclient import TestClient
from meridian.models import ContextTrace
from meridian.observability import CONTEXT_ASSEMBLY_TOTAL


@pytest.fixture
def mock_backend() -> AsyncMock:
    backend = AsyncMock()
    # Need pipeline mock
    pipeline = MagicMock()
    pipeline.set.return_value = None
    pipeline.sadd.return_value = None
    pipeline.expire.return_value = None
    # Async execute
    future = AsyncMock(return_value=None)
    pipeline.execute = future

    # Fix: pipeline() is called synchronously in context.py, so we Mock the method itself
    backend.pipeline = MagicMock(return_value=pipeline)

    backend.get.return_value = None  # Cache miss by default
    backend.set.return_value = None
    return backend


@pytest.mark.asyncio
async def test_context_trace_generation(mock_backend: AsyncMock) -> None:
    """Test that a trace is generated and saved on assembly."""

    @context(name="trace_test", cache_ttl=timedelta(seconds=10))
    async def my_context() -> str:
        return "hello world"

    # Inject backend
    setattr(my_context, "_cache_backend", mock_backend)

    # Execute
    ctx = await my_context()

    # Verification
    assert ctx.id

    # Check if trace was written
    # backend.set should be called with "trace:{id}"
    trace_key = f"trace:{ctx.id}"

    # We expect set call for trace.
    # Use await backend.set(...) in code. So we check mock_backend.set.assert_called()

    # Filter calls.
    # Note: backend.set is async mock, so calls are recorded.
    found = False
    for call in mock_backend.set.mock_calls:
        if call.args[0] == trace_key:
            found = True
            trace_json = call.args[1]
            trace = ContextTrace.model_validate_json(trace_json)
            assert trace.context_id == ctx.id
            assert trace.freshness_status == "guaranteed"
            assert trace.latency_ms >= 0  # Should be small but non-negative

    assert found, "Trace key was not written to backend"


@pytest.mark.asyncio
async def test_metrics_recording(mock_backend: AsyncMock) -> None:
    """Test that Prometheus counters are incremented."""

    # We can't easily reset global collectors in tests without side effects.
    # We retrieve current value and check increment.

    metric = CONTEXT_ASSEMBLY_TOTAL.labels(name="metric_test", status="success")
    before = metric._value.get()

    @context(name="metric_test")
    async def metric_func() -> str:
        return "metrics"

    await metric_func()

    after = metric._value.get()
    assert after == before + 1


def test_server_explain_endpoint() -> None:
    """Test the /explain endpoint."""
    store = MagicMock()
    # online_store needs to be async for get()
    store.online_store = AsyncMock()

    app = create_app(store)
    client = TestClient(app)

    trace_id = "test-uuid"
    trace_data = ContextTrace(
        context_id=trace_id,
        created_at=datetime(2025, 1, 1, tzinfo=None),
        latency_ms=100.0,
        token_usage=50,
        freshness_status="guaranteed",
        source_ids=["src1"],
        cost_usd=0.001,
        cache_hit=False,
    )

    # Mock backend return
    store.online_store.get.return_value = trace_data.model_dump_json().encode()

    # Call API
    # Note: API requires X-API-Key or dev-mode logic (which defaults to allowed if env var not set)
    response = client.get(f"/v1/context/{trace_id}/explain")
    assert response.status_code == 200
    data = response.json()
    assert data["context_id"] == trace_id
    assert data["token_usage"] == 50
    assert data["source_ids"] == ["src1"]
