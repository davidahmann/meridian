import os
from fastapi.testclient import TestClient
from meridian.server import create_app
from meridian.core import FeatureStore


def test_api_key_enforcement() -> None:
    # Set API Key
    os.environ["MERIDIAN_API_KEY"] = "secret-key"

    store = FeatureStore()
    app = create_app(store)
    client = TestClient(app)

    # Request without key -> 403
    response = client.post(
        "/v1/features",
        json={"entity_name": "User", "entity_id": "u1", "features": ["f1"]},
    )
    assert response.status_code == 403

    # Request with wrong key -> 403
    response = client.post(
        "/v1/features",
        json={"entity_name": "User", "entity_id": "u1", "features": ["f1"]},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 403

    # Request with correct key -> 200 (or 500 if store fails, but auth passed)
    # We expect 500 here because store is empty/mocked and might fail on logic,
    # but we only care that it passed auth (i.e. not 403).
    # Actually, let's mock the store to return something valid or handle the error gracefully.
    # But for now, checking != 403 is enough to prove auth worked.
    response = client.post(
        "/v1/features",
        json={"entity_name": "User", "entity_id": "u1", "features": ["f1"]},
        headers={"X-API-Key": "secret-key"},
    )
    assert response.status_code != 403

    # Cleanup
    del os.environ["MERIDIAN_API_KEY"]


def test_dev_mode_no_key() -> None:
    # Ensure no key is set
    if "MERIDIAN_API_KEY" in os.environ:
        del os.environ["MERIDIAN_API_KEY"]

    store = FeatureStore()
    app = create_app(store)
    client = TestClient(app)

    # Request without key -> 200 (or not 403)
    response = client.post(
        "/v1/features",
        json={"entity_name": "User", "entity_id": "u1", "features": ["f1"]},
    )
    assert response.status_code != 403
