import pytest
from httpx import AsyncClient, ASGITransport
from meridian.server import create_app
from meridian.core import FeatureStore, entity, feature
from meridian.store.online import InMemoryOnlineStore


@pytest.mark.asyncio
async def test_api_get_features() -> None:
    # 1. Setup Store
    store = FeatureStore(online_store=InMemoryOnlineStore())

    @entity(store)
    class User:
        user_id: str

    @feature(entity=User)
    def user_clicks(user_id: str) -> int:
        return 10

    # Pre-populate online store
    await store.online_store.set_online_features(
        entity_name="User", entity_id="u1", features={"user_clicks": 42}
    )

    # 2. Create App & Client
    app = create_app(store)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 3. Request Features
        response = await client.post(
            "/v1/features",
            json={
                "entity_name": "User",
                "entity_id": "u1",
                "features": ["user_clicks"],
            },
        )

    # 4. Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["user_clicks"] == 42


@pytest.mark.asyncio
async def test_api_health() -> None:
    store = FeatureStore()
    app = create_app(store)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_api_visualize_context() -> None:
    # 1. Setup Store with trace data
    store = FeatureStore(online_store=InMemoryOnlineStore())

    # Manually seed a trace
    from meridian.models import ContextTrace

    trace = ContextTrace(
        context_id="test_ctx_123",
        latency_ms=150,
        token_usage=500,
        freshness_status="guaranteed",
        source_ids=["src1", "src2"],
        stale_sources=[],
        cost_usd=0.002,
        cache_hit=False,
    )

    # Store directly in online store
    # Note: InMemory uses cache_storage for get()
    # Pydantic dump_json -> string, store expects bytes or string depending on impl
    # InMemoryOnlineStore.set takes bytes? Let's check impl. Core.py sets bytes.
    await store.online_store.set("trace:test_ctx_123", trace.model_dump_json().encode())

    # 2. Create App & Client
    app = create_app(store)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 3. Request Visualization
        response = await client.get("/v1/context/test_ctx_123/visualize")

    # 4. Assertions
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<!DOCTYPE html>" in response.text
    assert "test_ctx_123" in response.text
    assert "500" in response.text  # token usage
