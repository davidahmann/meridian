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
            "/features",
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
