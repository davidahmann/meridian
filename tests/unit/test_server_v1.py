import pytest
from fastapi.testclient import TestClient
from meridian.server import create_app
from meridian.core import FeatureStore
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def client() -> TestClient:
    store = MagicMock(spec=FeatureStore)
    store.online_store = MagicMock()
    # Mock get_online_features to return dummy data
    store.get_online_features = AsyncMock(return_value={"age": 30})

    app = create_app(store)
    return TestClient(app)


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_v1_features_batch(client: TestClient) -> None:
    payload = {"name": "User", "ids": ["u1", "u2"], "features": ["age"]}
    # No API key needed in dev mode if env var not set,
    # but get_api_key logic in server.py defaults to "dev-mode" if not configured.

    response = client.post("/v1/features/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "u1" in data
    assert "u2" in data
    assert data["u1"]["age"] == 30


def test_v1_features_single(client: TestClient) -> None:
    payload = {"entity_name": "User", "entity_id": "u1", "features": ["age"]}
    response = client.post("/v1/features", json=payload)
    assert response.status_code == 200
    assert response.json() == {"age": 30}
