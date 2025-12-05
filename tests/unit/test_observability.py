import pytest
from fastapi.testclient import TestClient
from meridian.server import create_app
from meridian.core import FeatureStore, entity, feature


@pytest.mark.asyncio
async def test_api_metrics() -> None:
    store = FeatureStore()

    @entity(store)
    class User:
        user_id: str

    @feature(entity=User)
    def test_feature(user_id: str) -> int:
        return 1

    app = create_app(store)
    client = TestClient(app)

    # Make a request to trigger metrics
    # This hits the FastAPI endpoint which calls store.get_online_features
    response = client.post(
        "/features",
        json={"entity_name": "User", "entity_id": "u1", "features": ["test_feature"]},
    )
    assert response.status_code == 200

    # Fetch metrics
    response = client.get("/metrics")
    assert response.status_code == 200

    # Check for server metrics
    assert "meridian_request_count" in response.text

    # Check for feature metrics
    assert "meridian_feature_requests_total" in response.text
    assert 'feature="test_feature"' in response.text
    assert 'status="compute_success"' in response.text
    assert "meridian_feature_latency_seconds" in response.text
